# -*- coding: utf-8 -*-
"""
3 sahte confluence senaryosu — katman kararlarını terminale basar, DERR SQL kanıtı.
Beklenen (kurallardan): S1 düşük parlaklık, S2 ALTIN, S3 REJECT.
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from mina_trading_journal import TradingJournal
from signal_bot.signal_guillotine import (
    evaluate_guillotine,
    evaluate_katman3,
    merter_has_sfp,
    parse_total_direction,
)
from signal_bot.signal_parser import parse_haluk_telegram, parse_merter

TEST_DB = os.path.join(_ROOT, "test_scenario_decisions.db")

SCENARIOS = [
    {
        "label": "TEST_S1",
        "title": "Senaryo 1: Merter UZUN, Asya, TOTAL yukarı, SFP yok",
        "session": "Asya",
        "merter_text": "$BTC için Long, giriş 65000, stop 63000",
        "haluk_text": (
            "TOTAL UPDATE\n"
            "TOTAL: ana yön yukarı, kanal içinde devam. "
            "Altlarda sorun yok, long yönlü bakış geçerli."
        ),
    },
    {
        "label": "TEST_S2",
        "title": "Senaryo 2: Merter LONG, New York, TOTAL yukarı, SFP var",
        "session": "New York",
        "merter_text": "$SFP için Long, giriş 0.85, stop 0.80",
        "haluk_text": (
            "TOTAL\n"
            "TOTAL yukarı — risk iştahı yüksek, SFP long uyumlu."
        ),
    },
    {
        "label": "TEST_S3",
        "title": "Senaryo 3: Merter LONG, Londra, TOTAL aşağı",
        "session": "Londra",
        "merter_text": "$ETH için Long, giriş 1900, stop 1850",
        "haluk_text": (
            "TOTAL\n"
            "TOTAL aşağı yönlü — longlara yaklaşma, baskı devam."
        ),
    },
]


def _print_block(title: str, data: dict) -> None:
    print(f"\n  [{title}]")
    print(json.dumps(data, ensure_ascii=False, indent=4))


def run_scenario(sc: dict, journal: TradingJournal) -> int:
    print("\n" + "=" * 72)
    print(sc["title"])
    print("=" * 72)

    # ── Katman 1 ──────────────────────────────────────────────────────
    merter_records = parse_merter(sc["merter_text"])
    haluk_records, pause = parse_haluk_telegram(sc["haluk_text"])
    total_dir = parse_total_direction(sc["haluk_text"])
    has_sfp = merter_has_sfp(sc["merter_text"], merter_records[0] if merter_records else None)

    k1 = {
        "layer": 1,
        "merter_parse_count": len(merter_records),
        "haluk_parse_count": len(haluk_records),
        "system_pause": pause,
        "merter_records": merter_records,
        "haluk_records": haluk_records,
        "total_direction_detected": total_dir,
        "has_sfp_detected": has_sfp,
    }
    _print_block("KATMAN 1 — Parser", k1)

    if not merter_records:
        print("  [KATMAN 1] Merter kaydı yok — pipeline durur.")
        return -1

    merter = merter_records[0]

    # ── Katman 2 ──────────────────────────────────────────────────────
    k2 = evaluate_guillotine(
        merter_record=merter,
        haluk_macro_text=sc["haluk_text"],
        session=sc["session"],
        merter_raw_text=sc["merter_text"],
    )
    _print_block("KATMAN 2 — Giyotin", k2)

    # ── Katman 3 ──────────────────────────────────────────────────────
    k3 = evaluate_katman3(k2)
    _print_block("KATMAN 3 — Aksiyon", k3)

    print(f"\n  >>> SONUÇ ETİKETİ: {k2.get('label')} (parlaklık={k2.get('brightness')})")

    row_id = journal.log_signal_decision(
        scenario_label=sc["label"],
        merter_symbol=merter.get("symbol", "?"),
        merter_direction=merter.get("direction", "?"),
        trading_session=sc["session"],
        has_sfp=has_sfp,
        total_direction=total_dir,
        k1=k1,
        k2=k2,
        k3=k3,
    )
    print(f"  >>> DERR signal_decisions id={row_id}")
    return row_id


def sql_proof(journal: TradingJournal) -> None:
    print("\n" + "=" * 72)
    print("DERR SQL KANIT — signal_decisions")
    print("=" * 72)
    sql = (
        "SELECT id, scenario_label, merter_symbol, merter_direction, "
        "trading_session, has_sfp, total_direction, k2_label, k2_brightness, "
        "k2_verdict, k3_action, final_label "
        "FROM signal_decisions "
        "WHERE scenario_label LIKE 'TEST_S%' "
        "ORDER BY id"
    )
    print(f"\nSQL:\n{sql}\n")
    cur = journal.conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    print("-" * 100)
    for row in rows:
        print(" | ".join(str(row[c]) for c in cols))
    print(f"\nToplam kayıt: {len(rows)} (beklenen: 3)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    journal = TradingJournal(db_path=TEST_DB)
    ids = []
    for sc in SCENARIOS:
        rid = run_scenario(sc, journal)
        if rid > 0:
            ids.append(rid)

    sql_proof(journal)
    journal.close()

    print("\n" + "=" * 72)
    print("BEKLENEN vs ÜRETİLEN")
    print("=" * 72)
    cur = __import__("sqlite3").connect(TEST_DB)
    cur.row_factory = __import__("sqlite3").Row
    expected = {
        "TEST_S1": "DÜŞÜK_PARLAKLIK",
        "TEST_S2": "ALTIN_SİNYAL",
        "TEST_S3": "REJECT",
    }
    for label, exp in expected.items():
        row = cur.execute(
            "SELECT k2_label FROM signal_decisions WHERE scenario_label=?",
            (label,),
        ).fetchone()
        got = row["k2_label"] if row else "?"
        ok = "OK" if got == exp else "FARK"
        print(f"  {label}: beklenen={exp}  üretilen={got}  [{ok}]")
    cur.close()


if __name__ == "__main__":
    main()
