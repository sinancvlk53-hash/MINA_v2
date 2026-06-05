#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stale D1 marker temizliği — journal defense_triggered=0 iken defense_levels>0."""
import json
import os
import sqlite3

ROOT = "/root/MINA_v2"
DB = f"{ROOT}/mina_trading_journal.db"
DEF = f"{ROOT}/defense_levels.json"
STATE = f"{ROOT}/position_states.json"


def main() -> None:
    defense = json.load(open(DEF, encoding="utf-8")) if os.path.isfile(DEF) else {}
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    fixed = []
    for key, lvl in list(defense.items()):
        if int(lvl or 0) <= 0:
            continue
        sym, side = key.rsplit("_", 1)
        row = conn.execute(
            "SELECT defense_triggered FROM trades WHERE symbol=? AND side=? AND status='open' ORDER BY id DESC LIMIT 1",
            (sym, side),
        ).fetchone()
        jdef = int(row["defense_triggered"] or 0) if row else 0
        if jdef >= 1:
            continue
        print(f"RESET stale {key}: defense_levels={lvl} -> 0 (journal defense_triggered={jdef})")
        defense[key] = 0
        fixed.append(key)

    if fixed:
        with open(DEF, "w", encoding="utf-8") as f:
            json.dump(defense, f, indent=2, ensure_ascii=False)
            f.write("\n")

    if fixed and os.path.isfile(STATE):
        st = json.load(open(STATE, encoding="utf-8"))
        changed = False
        for sym, s in st.items():
            if not isinstance(s, dict):
                continue
            for k in fixed:
                if k.startswith(sym + "_") or k.split("_")[0] == sym:
                    if int(s.get("defense_stage") or 0) >= 1:
                        s["defense_stage"] = 0
                        changed = True
                        print(f"RESET position_states {sym} defense_stage -> 0")
        if changed:
            with open(STATE, "w", encoding="utf-8") as f:
                json.dump(st, f, indent=2, ensure_ascii=False)
                f.write("\n")

    conn.close()
    print("done, fixed:", fixed or "none")


if __name__ == "__main__":
    main()
