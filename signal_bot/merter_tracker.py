# -*- coding: utf-8 -*-
"""
Merter Tracker — Bağımsız simülasyon motoru.
Ana motora dokunmaz. listener.py confluence tetikleyince open_simulated_position() çağırır.
2x / 4x / 5x kaldıraç aynı anda simüle edilir.
"""
import sys
import os
import json
import time
import asyncio
import atexit
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

from telegram_bot import send_notification
from config import BinanceConfig

# ── Sabitler ─────────────────────────────────────────────────────────────────
_DIR               = os.path.dirname(os.path.abspath(__file__))
SIMULATED_FILE     = os.path.join(_DIR, 'simulated_positions.json')
LOCK_FILE          = os.path.join(_DIR, 'merter_tracker.lock')
TIMEOUT_H          = 6            # pozisyon timeout (saat)
FUNDING_INTERVAL_S = 8 * 3600     # funding 8 saatte bir
SLIPPAGE           = 0.0005       # %0.05 mark price slippage
POLL_INTERVAL      = 30           # izleme döngüsü (saniye)
SIM_SL_4X          = -15.0        # 4x simülasyon max zarar (coin %)
REPORT_INTERVAL_S  = 24 * 3600    # günlük rapor aralığı
MAX_SNAPSHOTS      = 200          # pozisyon başına max snapshot

# Engine kurallarından türetilmiş simülasyon parametreleri:
#   2x → coin -3% stop | 4x → savunma (D1 coin -5%, sim stop coin -15%) | 5x → coin -2% stop
SIM_RULES = {
    '2x': {'lev': 2, 'stop_pct': -3.0, 'tp1_pct': 3.0, 'tp2_pct': 5.0, 'd1_pct': None},
    '4x': {'lev': 4, 'stop_pct': None, 'tp1_pct': 3.0, 'tp2_pct': 5.0, 'd1_pct': -5.0},
    '5x': {'lev': 5, 'stop_pct': -2.0, 'tp1_pct': 3.0, 'tp2_pct': 5.0, 'd1_pct': None},
}

# ── Dosya I/O ─────────────────────────────────────────────────────────────────

def load_simulated() -> dict:
    try:
        with open(SIMULATED_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_simulated(data: dict) -> None:
    with open(SIMULATED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── Lock ──────────────────────────────────────────────────────────────────────

def _acquire_lock() -> bool:
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                old_pid = int(f.read().strip())
            try:
                import psutil
                alive = psutil.pid_exists(old_pid)
            except ImportError:
                import subprocess
                alive = subprocess.run(
                    ['tasklist', '/FI', f'PID eq {old_pid}'],
                    capture_output=True, text=True
                ).returncode == 0
            if alive:
                print(f"merter_tracker zaten çalışıyor (PID {old_pid}). Çıkılıyor.")
                return False
        except Exception:
            pass
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    atexit.register(_release_lock)
    return True

def _release_lock():
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass

# ── Binance Yardımcıları ──────────────────────────────────────────────────────

def get_mark_price(client, symbol: str) -> float:
    """Mark price al, başarısız olursa last price'a fallback."""
    try:
        r = client.futures_mark_price(symbol=symbol)
        if isinstance(r, dict):
            return float(r.get('markPrice') or r['price'])
        for item in r:
            if item.get('symbol') == symbol:
                return float(item['markPrice'])
    except Exception:
        pass
    r = client.futures_symbol_ticker(symbol=symbol)
    if isinstance(r, dict):
        return float(r['price'])
    for item in r:
        if item.get('symbol') == symbol:
            return float(item['price'])
    raise ValueError(f"{symbol} mark price alınamadı")


def get_funding_rate(client, symbol: str) -> float:
    """Mevcut funding rate'i döndür (örn: 0.0001 = %0.01/8h)."""
    try:
        data = client.futures_funding_rate(symbol=symbol, limit=1)
        if data:
            return float(data[0]['fundingRate'])
    except Exception:
        pass
    return 0.0

# ── Pozisyon Açma (listener.py'den çağrılır) ──────────────────────────────────

def open_simulated_position(coin: str, side: str, source: str) -> str | None:
    """
    Confluence anında çağrılır.
    Mark price + %0.05 slippage ile 2x/4x/5x kaldıraç pozisyonu kaydeder.
    """
    config = BinanceConfig()
    client = config.get_client()

    try:
        mark = get_mark_price(client, coin)
    except Exception as e:
        print(f"[TRACKER] {coin} fiyat alınamadı: {e}")
        return None

    entry = mark * (1 + SLIPPAGE) if side == 'LONG' else mark * (1 - SLIPPAGE)

    now_ts  = time.time()
    suffix  = datetime.now().strftime('%H%M%S')
    pos_key = f"{coin}_{side}_{suffix}"

    lev_init = {
        'status':          'OPEN',
        'tp1_hit':         False,
        'tp2_hit':         False,
        'd1_triggered':    False,
        'd1_price':        None,
        'funding_pct':     0.0,       # kümülatif funding (coin % cinsinden)
        'last_funding_ts': now_ts,
        'close_coin_pct':  None,
        'close_roe':       None,
    }

    pos = {
        'coin':        coin,
        'side':        side,
        'source':      source,
        'mark_price':  round(mark,  6),
        'entry_price': round(entry, 6),
        'open_time':   datetime.now().isoformat(),
        'open_ts':     now_ts,
        'leverages':   {lk: dict(lev_init) for lk in SIM_RULES},
        'snapshots':   [],
    }

    sims          = load_simulated()
    sims[pos_key] = pos
    save_simulated(sims)

    print(f"[TRACKER] Açıldı: {coin} {side} Mark:${mark:.4f} → Giriş:${entry:.4f} ({source})")
    send_notification(
        f"📊 *SİMÜLASYON AÇILDI*\n"
        f"📌 {coin} {side} | 2x / 4x / 5x\n"
        f"💰 Mark: ${mark:.4f} → Giriş: ${entry:.4f} (slippage +%0.05)\n"
        f"🔗 Kaynak: {source}\n"
        f"⏱ Timeout: {TIMEOUT_H}h | D1(4x): coin ≤ -5%"
    )
    return pos_key

# ── Ana İzleme Döngüsü ────────────────────────────────────────────────────────

async def track_positions():
    config      = BinanceConfig()
    client      = config.get_client()
    last_report = 0.0

    while True:
        try:
            sims    = load_simulated()
            changed = False

            for pos_key, pos in sims.items():
                # Tüm kaldıraç simülasyonları kapandıysa atla
                if all(lev['status'] != 'OPEN' for lev in pos['leverages'].values()):
                    continue

                coin      = pos['coin']
                side      = pos['side']
                entry     = pos['entry_price']
                open_ts   = pos['open_ts']
                elapsed_h = (time.time() - open_ts) / 3600

                try:
                    mark = get_mark_price(client, coin)
                except Exception:
                    continue

                # Coin % hareketi (entry'den, slippage dahil)
                coin_pct = ((mark - entry) / entry * 100
                            if side == 'LONG'
                            else (entry - mark) / entry * 100)

                # Snapshot (max MAX_SNAPSHOTS)
                if len(pos['snapshots']) < MAX_SNAPSHOTS:
                    pos['snapshots'].append({
                        't': datetime.now().strftime('%H:%M'),
                        'p': round(mark, 4),
                        'c': round(coin_pct, 2),
                    })
                    changed = True

                for lev_key, lev in pos['leverages'].items():
                    if lev['status'] != 'OPEN':
                        continue

                    rules   = SIM_RULES[lev_key]
                    updated = False
                    notifs  = []

                    # ── Funding rate (8 saatte bir) ───────────────────────────
                    if time.time() - lev['last_funding_ts'] >= FUNDING_INTERVAL_S:
                        fr = get_funding_rate(client, coin)
                        # LONG: pozitif fr öder (negatif alır); SHORT: tersi
                        adjustment = (-fr if side == 'LONG' else fr) * 100
                        lev['funding_pct']     += adjustment
                        lev['last_funding_ts']  = time.time()
                        updated = True

                    # Efektif coin % (funding dahil — rapor için)
                    eff_pct = coin_pct + lev['funding_pct']
                    roe     = eff_pct * rules['lev']

                    # ── TIMEOUT ───────────────────────────────────────────────
                    if elapsed_h >= TIMEOUT_H:
                        lev.update(status='TIMEOUT',
                                   close_coin_pct=round(coin_pct, 3),
                                   close_roe=round(roe, 2))
                        updated = True
                        notifs.append(
                            f"⏰ *TIMEOUT — {coin} {side} [{lev_key}]*\n"
                            f"📊 Coin: {coin_pct:+.2f}% | ROE: {roe:+.2f}%\n"
                            f"⏱ {elapsed_h:.1f}h sonra kapandı | {pos['source']}"
                        )

                    # ── STOP LOSS (2x, 5x) ────────────────────────────────────
                    elif rules['stop_pct'] is not None and coin_pct <= rules['stop_pct']:
                        lev.update(status='SL',
                                   close_coin_pct=round(coin_pct, 3),
                                   close_roe=round(roe, 2))
                        updated = True
                        notifs.append(
                            f"🛑 *STOP LOSS — {coin} {side} [{lev_key}]*\n"
                            f"📊 Coin: {coin_pct:+.2f}% | ROE: {roe:+.2f}%\n"
                            f"💸 Kaynak: {pos['source']}"
                        )

                    # ── 4x sim stop (D3 eşdeğeri: coin -15%) ─────────────────
                    elif rules['stop_pct'] is None and coin_pct <= SIM_SL_4X:
                        lev.update(status='SL',
                                   close_coin_pct=round(coin_pct, 3),
                                   close_roe=round(roe, 2))
                        updated = True
                        notifs.append(
                            f"💥 *D3 LİMİT — {coin} {side} [{lev_key}]*\n"
                            f"📊 Coin: {coin_pct:+.2f}% | ROE: {roe:+.2f}%\n"
                            f"🚨 Sim stop {SIM_SL_4X}% aşıldı | {pos['source']}"
                        )

                    else:
                        # ── D1 tetikleme (4x) ─────────────────────────────────
                        if (rules['d1_pct'] is not None
                                and not lev['d1_triggered']
                                and coin_pct <= rules['d1_pct']):
                            lev['d1_triggered'] = True
                            lev['d1_price']     = round(mark, 4)
                            updated = True
                            print(f"[TRACKER] D1 TETİKLENDİ: {coin} {side} [{lev_key}] "
                                  f"coin {coin_pct:+.2f}%")

                        # ── TP1 ───────────────────────────────────────────────
                        if not lev['tp1_hit'] and coin_pct >= rules['tp1_pct']:
                            lev['tp1_hit'] = True
                            updated = True

                        # ── TP2 (TP1 sonrası veya fiyat direkt +5% geçtiyse) ──
                        if lev['tp1_hit'] and not lev['tp2_hit'] and coin_pct >= rules['tp2_pct']:
                            result = 'DEF_WIN' if lev['d1_triggered'] else 'CLEAN_WIN'
                            lev.update(status=result,
                                       tp2_hit=True,
                                       close_coin_pct=round(coin_pct, 3),
                                       close_roe=round(roe, 2))
                            updated = True
                            icon  = '🛡️' if result == 'DEF_WIN' else '🎯'
                            label = 'DEFANSİF KAZANÇ' if result == 'DEF_WIN' else 'CLEAN WIN'
                            d1_note = (' ✔ D1 tetiklendi → kazandı'
                                       if result == 'DEF_WIN' else '')
                            notifs.append(
                                f"{icon} *{label} — {coin} {side} [{lev_key}]*\n"
                                f"📊 Coin: {coin_pct:+.2f}% | ROE: {roe:+.2f}%{d1_note}\n"
                                f"💡 Kaynak: {pos['source']}"
                            )

                    for n in notifs:
                        send_notification(n)

                    if updated:
                        changed = True

                if changed:
                    sims[pos_key] = pos

            if changed:
                save_simulated(sims)

            # Günlük rapor kontrolü
            if time.time() - last_report >= REPORT_INTERVAL_S:
                _send_daily_report(load_simulated())
                last_report = time.time()

        except Exception as e:
            print(f"[TRACKER] Döngü hatası: {e}")

        await asyncio.sleep(POLL_INTERVAL)

# ── Rapor ─────────────────────────────────────────────────────────────────────

def _send_daily_report(sims: dict):
    """Kapalı pozisyonlardan kaldıraç ve kaynak bazında özet üret."""
    closed = [p for p in sims.values()
              if all(lev['status'] != 'OPEN' for lev in p['leverages'].values())]
    if not closed:
        return

    lines = [
        f"📈 *MERTER TRACKER RAPORU*",
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        f"📊 Toplam kapalı sinyal: {len(closed)}\n",
    ]

    for lev_key in ('2x', '4x', '5x'):
        counts = {'CLEAN_WIN': 0, 'DEF_WIN': 0, 'SL': 0, 'TIMEOUT': 0}
        roes   = []
        for pos in closed:
            lev = pos['leverages'].get(lev_key, {})
            st  = lev.get('status', '')
            if st in counts:
                counts[st] += 1
            if lev.get('close_roe') is not None:
                roes.append(lev['close_roe'])

        total    = sum(counts.values()) or 1
        win_rate = (counts['CLEAN_WIN'] + counts['DEF_WIN']) / total * 100
        avg_roe  = sum(roes) / len(roes) if roes else 0.0
        lines.append(
            f"*{lev_key}* | 🎯{counts['CLEAN_WIN']} 🛡️{counts['DEF_WIN']} "
            f"🛑{counts['SL']} ⏰{counts['TIMEOUT']} "
            f"| Win: %{win_rate:.0f} | OrtROE: {avg_roe:+.1f}%"
        )

    # Kaynak bazında (4x referans)
    src_stats: dict = {}
    for pos in closed:
        src = pos.get('source', '?')
        src_stats.setdefault(src, {'total': 0, 'win': 0})
        src_stats[src]['total'] += 1
        lev4_status = pos['leverages'].get('4x', {}).get('status', '')
        if lev4_status in ('CLEAN_WIN', 'DEF_WIN'):
            src_stats[src]['win'] += 1

    lines.append('\n*Kaynak (4x referans):*')
    for src, s in src_stats.items():
        wr = s['win'] / s['total'] * 100 if s['total'] else 0
        lines.append(f"  {src}: {s['total']} sinyal | %{wr:.0f} win")

    send_notification('\n'.join(lines))


def send_report_now():
    """Manuel rapor tetikleyici (dışarıdan çağrılabilir)."""
    _send_daily_report(load_simulated())


# ── Giriş Noktası ─────────────────────────────────────────────────────────────

async def _main():
    if not _acquire_lock():
        return
    print(f"[TRACKER] Başlatıldı PID:{os.getpid()} | "
          f"poll:{POLL_INTERVAL}s timeout:{TIMEOUT_H}h slippage:%0.05")
    send_notification(
        f"📊 *MERTER TRACKER BAŞLADI*\n"
        f"⚙️ Poll: {POLL_INTERVAL}s | Timeout: {TIMEOUT_H}h\n"
        f"📐 Kaldıraçlar: 2x / 4x / 5x\n"
        f"💸 Slippage: %0.05 | Funding: 8h'de bir"
    )
    await track_positions()


if __name__ == '__main__':
    asyncio.run(_main())
