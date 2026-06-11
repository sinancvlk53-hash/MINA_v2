# -*- coding: utf-8 -*-
"""Haluk yayın özeti ve coin analizi — SQLite şema + kayıt."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT, "mina_trading_journal.db")
TR_TZ = timezone(timedelta(hours=3))

_SUMMARY_EXTRA_COLS = (
    ("video_id", "TEXT"),
    ("video_url", "TEXT"),
    ("genel_piyasa_yonu", "TEXT"),
    ("onemli_haberler", "TEXT"),
    ("incelenen_coinler", "TEXT"),
    ("ham_json", "TEXT"),
    ("transkript_path", "TEXT"),
    ("whisper_model", "TEXT"),
    ("sure_saniye", "INTEGER"),
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn


def init_yayin_tables() -> None:
    """haluk_yayin_summaries genişlet + haluk_coin_analizleri oluştur."""
    conn = _conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS haluk_yayin_summaries (
                message_id INTEGER PRIMARY KEY,
                video_date TEXT,
                summary_sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(haluk_yayin_summaries)").fetchall()
        }
        for col, typ in _SUMMARY_EXTRA_COLS:
            if col not in existing:
                conn.execute(f"ALTER TABLE haluk_yayin_summaries ADD COLUMN {col} {typ}")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS haluk_coin_analizleri (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                video_id TEXT,
                video_date TEXT,
                coin TEXT,
                strateji TEXT,
                destekler TEXT,
                direncler TEXT,
                kritik_seviye REAL,
                formasyon TEXT,
                baz_fiyat REAL,
                fiyat_1s REAL,
                fiyat_4s REAL,
                fiyat_24s REAL,
                basari_1s TEXT,
                basari_4s TEXT,
                basari_24s TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_haluk_coin_msg ON haluk_coin_analizleri(message_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_haluk_coin_created ON haluk_coin_analizleri(created_at)"
        )
        conn.commit()
    finally:
        conn.close()


def save_yayin_analysis(
    *,
    message_id: int,
    video_id: str,
    video_url: str,
    video_date: str,
    data: Dict[str, Any],
    ham_json: str,
    transkript_path: str,
    whisper_model: str,
    sure_saniye: int,
) -> List[int]:
    """Özet + coin satırlarını kaydet. Eklenen coin satır id'lerini döndür."""
    init_yayin_tables()
    onemli = data.get("onemli_haberler") or []
    coinler = data.get("incelenen_coinler") or []

    conn = _conn()
    coin_ids: List[int] = []
    try:
        conn.execute(
            """
            INSERT INTO haluk_yayin_summaries (
                message_id, video_date, video_id, video_url,
                genel_piyasa_yonu, onemli_haberler, incelenen_coinler,
                ham_json, transkript_path, whisper_model, sure_saniye,
                summary_sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(message_id) DO UPDATE SET
                video_date=excluded.video_date,
                video_id=excluded.video_id,
                video_url=excluded.video_url,
                genel_piyasa_yonu=excluded.genel_piyasa_yonu,
                onemli_haberler=excluded.onemli_haberler,
                incelenen_coinler=excluded.incelenen_coinler,
                ham_json=excluded.ham_json,
                transkript_path=excluded.transkript_path,
                whisper_model=excluded.whisper_model,
                sure_saniye=excluded.sure_saniye,
                summary_sent_at=CURRENT_TIMESTAMP
            """,
            (
                message_id,
                video_date,
                video_id,
                video_url,
                str(data.get("genel_piyasa_yonu") or ""),
                json.dumps(onemli, ensure_ascii=False),
                json.dumps(coinler, ensure_ascii=False),
                ham_json,
                transkript_path,
                whisper_model,
                sure_saniye,
            ),
        )

        for item in coinler:
            if not isinstance(item, dict):
                continue
            coin = str(item.get("coin") or "").strip().upper()
            if not coin:
                continue
            destekler = item.get("destekler")
            direncler = item.get("direncler")
            kritik = item.get("kritik_seviye")
            try:
                kritik_val = float(kritik) if kritik is not None and kritik != "" else None
            except (TypeError, ValueError):
                kritik_val = None

            cur = conn.execute(
                """
                INSERT INTO haluk_coin_analizleri (
                    message_id, video_id, video_date, coin, strateji,
                    destekler, direncler, kritik_seviye, formasyon
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    video_id,
                    video_date,
                    coin,
                    str(item.get("strateji") or ""),
                    json.dumps(destekler, ensure_ascii=False) if destekler is not None else None,
                    json.dumps(direncler, ensure_ascii=False) if direncler is not None else None,
                    kritik_val,
                    str(item.get("formasyon") or ""),
                ),
            )
            coin_ids.append(int(cur.lastrowid))

        conn.commit()
    finally:
        conn.close()
    return coin_ids


def update_coin_baz_fiyat(row_id: int, baz_fiyat: float) -> None:
    conn = _conn()
    try:
        conn.execute(
            "UPDATE haluk_coin_analizleri SET baz_fiyat=? WHERE id=?",
            (baz_fiyat, row_id),
        )
        conn.commit()
    finally:
        conn.close()


def pending_price_checks() -> List[Dict[str, Any]]:
    """1s / 4s / 24s fiyat güncellemesi bekleyen satırlar."""
    init_yayin_tables()
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT id, coin, strateji, baz_fiyat, fiyat_1s, fiyat_4s, fiyat_24s,
                   basari_1s, basari_4s, basari_24s, created_at
            FROM haluk_coin_analizleri
            WHERE baz_fiyat IS NOT NULL
              AND (fiyat_24s IS NULL OR fiyat_4s IS NULL OR fiyat_1s IS NULL)
            ORDER BY id
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_coin_interval_price(
    row_id: int,
    *,
    interval: str,
    fiyat: float,
    basari: str,
) -> None:
    col_price = {"1s": "fiyat_1s", "4s": "fiyat_4s", "24s": "fiyat_24s"}[interval]
    col_basari = {"1s": "basari_1s", "4s": "basari_4s", "24s": "basari_24s"}[interval]
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE haluk_coin_analizleri SET {col_price}=?, {col_basari}=? WHERE id=?",
            (fiyat, basari, row_id),
        )
        conn.commit()
    finally:
        conn.close()
