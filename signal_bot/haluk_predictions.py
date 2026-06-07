# -*- coding: utf-8 -*-
"""Haluk Hoca tarihe bağlı tahminler — haluk_predictions tablosu."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT, "mina_trading_journal.db")
TR_TZ = timezone(timedelta(hours=3))


def _conn() -> sqlite3.Connection:
    import sys
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from mina_trading_journal import TradingJournal
    return TradingJournal.connect(DB_PATH)


def init_predictions_table() -> None:
    conn = _conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS haluk_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                tarih TEXT NOT NULL,
                tahmin TEXT NOT NULL,
                hedef_tarih TEXT NOT NULL,
                sonuc TEXT,
                reminded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_haluk_pred_hedef ON haluk_predictions(hedef_tarih)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS haluk_yayin_summaries (
                message_id INTEGER PRIMARY KEY,
                video_date TEXT,
                summary_sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_prediction(
    *,
    message_id: Optional[int],
    tarih: str,
    tahmin: str,
    hedef_tarih: str,
) -> int:
    init_predictions_table()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO haluk_predictions (message_id, tarih, tahmin, hedef_tarih)
            VALUES (?, ?, ?, ?)
            """,
            (message_id, tarih, tahmin, hedef_tarih),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def insert_predictions_batch(
    items: List[Dict[str, Any]],
    *,
    message_id: Optional[int],
    tarih: str,
) -> int:
    n = 0
    for item in items:
        tahmin = (item.get("tahmin") or item.get("prediction") or "").strip()
        hedef = (item.get("hedef_tarih") or item.get("target_date") or "").strip()
        if not tahmin or not hedef:
            continue
        insert_prediction(
            message_id=message_id,
            tarih=tarih,
            tahmin=tahmin,
            hedef_tarih=hedef[:10],
        )
        n += 1
    return n


def mark_summary_sent(message_id: int, video_date: str = "") -> None:
    init_predictions_table()
    conn = _conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO haluk_yayin_summaries (message_id, video_date)
            VALUES (?, ?)
            """,
            (message_id, video_date),
        )
        conn.commit()
    finally:
        conn.close()


def summary_already_sent(message_id: int) -> bool:
    init_predictions_table()
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM haluk_yayin_summaries WHERE message_id=?",
            (message_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def due_predictions_today(today: Optional[str] = None) -> List[Dict[str, Any]]:
    init_predictions_table()
    today = today or datetime.now(TR_TZ).strftime("%Y-%m-%d")
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT id, message_id, tarih, tahmin, hedef_tarih, sonuc
            FROM haluk_predictions
            WHERE hedef_tarih = ? AND reminded = 0
            ORDER BY id
            """,
            (today,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_reminded(prediction_id: int) -> None:
    conn = _conn()
    try:
        conn.execute(
            "UPDATE haluk_predictions SET reminded=1 WHERE id=?",
            (prediction_id,),
        )
        conn.commit()
    finally:
        conn.close()


def send_prediction_reminders() -> int:
    """Hedef tarihi bugün olan tahminler için Telegram hatırlatması."""
    try:
        from tools.telegram_bot import send_notification
    except Exception:
        send_notification = None

    sent = 0
    for row in due_predictions_today():
        msg = (
            "📅 HATIRLATMA: Hoca "
            f"{row['tarih']} tarihinde şunu demişti: {row['tahmin']}. "
            "Bugün o tarih!"
        )
        print(f"[HALUK PRED] {msg}")
        if send_notification:
            send_notification(msg)
        mark_reminded(int(row["id"]))
        sent += 1
    return sent
