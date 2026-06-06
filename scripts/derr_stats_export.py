#!/usr/bin/env python3
import json, os, sqlite3
ROOT = "/root/MINA_v2"
db = os.path.join(ROOT, "mina_trading_journal.db")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
c = conn.cursor()
total = c.execute("SELECT COUNT(*) n FROM trades").fetchone()["n"]
closed = c.execute("SELECT COUNT(*) n FROM trades WHERE status='closed'").fetchone()["n"]
open_c = c.execute("SELECT COUNT(*) n FROM trades WHERE status='open'").fetchone()["n"]
realized = c.execute("SELECT COALESCE(SUM(pnl_usdt),0) s FROM trades WHERE status='closed'").fetchone()["s"]
wins = c.execute("SELECT COUNT(*) n FROM trades WHERE status='closed' AND pnl_usdt>0").fetchone()["n"]
losses = c.execute("SELECT COUNT(*) n FROM trades WHERE status='closed' AND pnl_usdt<0").fetchone()["n"]
flat = c.execute("SELECT COUNT(*) n FROM trades WHERE status='closed' AND (pnl_usdt=0 OR pnl_usdt IS NULL)").fetchone()["n"]
best = c.execute(
    "SELECT id,symbol,side,pnl_usdt,close_reason,open_time,close_time FROM trades "
    "WHERE status='closed' AND pnl_usdt IS NOT NULL ORDER BY pnl_usdt DESC LIMIT 3"
).fetchall()
worst = c.execute(
    "SELECT id,symbol,side,pnl_usdt,close_reason,open_time,close_time FROM trades "
    "WHERE status='closed' AND pnl_usdt IS NOT NULL ORDER BY pnl_usdt ASC LIMIT 3"
).fetchall()
by_src = c.execute(
    "SELECT signal_source, COUNT(*) n, "
    "SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) closed_n, "
    "COALESCE(SUM(CASE WHEN status='closed' THEN pnl_usdt ELSE 0 END),0) pnl "
    "FROM trades GROUP BY signal_source ORDER BY n DESC"
).fetchall()
by_reason = c.execute(
    "SELECT close_reason, COUNT(*) n, COALESCE(SUM(pnl_usdt),0) pnl "
    "FROM trades WHERE status='closed' GROUP BY close_reason ORDER BY n DESC"
).fetchall()
print(json.dumps({
    "total_trades": total,
    "open": open_c,
    "closed": closed,
    "realized_pnl_usdt": round(float(realized or 0), 4),
    "wins": wins,
    "losses": losses,
    "flat_or_null": flat,
    "win_rate_pct": round(wins / (wins + losses) * 100, 2) if (wins + losses) else None,
    "best": [dict(r) for r in best],
    "worst": [dict(r) for r in worst],
    "by_source": [dict(r) for r in by_src],
    "by_close_reason": [dict(r) for r in by_reason],
}, ensure_ascii=False, indent=2, default=str))
conn.close()
