# -*- coding: utf-8 -*-
"""
MİNA v2 - Sistem Monitor
Log takibi + Binance API anlık durum
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BinanceConfig
from datetime import datetime

LOG_FILE         = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'mina_bot.log')
DEFENSE_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'defense_levels.json')
INITIAL_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'initial_margins.json')
TP_FILE          = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tp_levels.json')

REPORT_INTERVAL  = 300   # 5 dakikada bir tam rapor
ALERT_ROE        = -70.0 # ROE eşiği
SLOT_LIMIT_RATIO = 1.0   # slot'un %100'ü

# ─── YARDIMCI ────────────────────────────────────────────────────────────────

def now():
    return datetime.now().strftime('%H:%M:%S')

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

def ts():
    return f"[{now()}]"

def sep(char='─', n=65):
    print(char * n)

# ─── LOG TAKİP ───────────────────────────────────────────────────────────────

def watch_log(path, last_pos):
    """Log'da yeni satır var mı kontrol et, kritik olayları bas."""
    alerts = []
    try:
        size = os.path.getsize(path)
    except:
        return last_pos, alerts

    if size <= last_pos:
        return last_pos, alerts

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        f.seek(last_pos)
        new_lines = f.readlines()
        last_pos = f.tell()

    for line in new_lines:
        line = line.rstrip()
        if not line:
            continue

        # Savunma
        if 'SAVUNMA' in line:
            if 'MARGIN HATASI' in line or 'BAŞARISIZ' in line or '-4054' in line:
                print(f"\n🚨 KRİTİK HATA! {line}")
                alerts.append(('D3_FAIL', line))
            elif 'SAVUNMA 3' in line and 'MARGIN eklendi' in line:
                print(f"\n✅ D3 BAŞARILI! {line}")
                alerts.append(('D3_OK', line))
            elif 'SAVUNMA' in line and 'eklendi' in line:
                print(f"\n🛡️  {line}")
        # TP
        elif 'TP1' in line or 'TP2' in line:
            print(f"\n💰 {line}")
        # Trailing
        elif 'TRAILING' in line:
            print(f"\n🎯 {line}")
        # SL
        elif 'STOP LOSS' in line:
            print(f"\n🛑 {line}")
        # Hata
        elif 'ERROR' in line or 'HATA' in line:
            print(f"\n❌ {line}")
            alerts.append(('ERROR', line))

    return last_pos, alerts

# ─── POZISYON RAPORU ─────────────────────────────────────────────────────────

def full_report(client):
    sep('═')
    print(f"  {ts()} — 5 DAKİKALIK RAPOR")
    sep('═')

    try:
        # Bakiye
        bal_data = client.futures_account_balance()
        balance  = float(next(x for x in bal_data if x['asset'] == 'USDT')['balance'])
        slot_size = balance / 10
        slot_limit = slot_size * SLOT_LIMIT_RATIO

        print(f"💰 Bakiye: {balance:.2f} USDT  |  Slot: {slot_size:.2f} USDT  |  Limit: {slot_limit:.2f} USDT")

        # JSON dosyaları
        defense_lvls  = load_json(DEFENSE_FILE)
        init_margins  = load_json(INITIAL_FILE)
        tp_lvls       = load_json(TP_FILE)

        # Açık pozisyonlar
        positions = client.futures_position_information()
        open_pos  = [p for p in positions if float(p['positionAmt']) != 0]

        print(f"📊 Açık Pozisyon: {len(open_pos)}\n")

        if not open_pos:
            print("  ── Açık pozisyon yok ──")
            sep()
            return

        # Başlık
        print(f"  {'Coin':<12} {'Side':<6} {'Lev':>4}  {'ROE':>8}  {'PnL':>10}  {'Margin':>9}  {'D':>2}  {'TP':>3}  {'Lim?'}")
        print(f"  {'─'*12} {'─'*6} {'─'*4}  {'─'*8}  {'─'*10}  {'─'*9}  {'─'*2}  {'─'*3}  {'─'*5}")

        critical = []

        for p in open_pos:
            symbol  = p['symbol']
            side    = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
            lev     = int(p['leverage'])
            upnl    = float(p['unRealizedProfit'])
            iso_mrg = float(p['isolatedMargin'])

            pos_key = f"{symbol}_{side}"
            init_m  = init_margins.get(pos_key, iso_mrg)
            roe     = (upnl / init_m * 100) if init_m > 0 else 0.0
            d_lvl   = defense_lvls.get(pos_key, 0)
            tp_lvl  = tp_lvls.get(pos_key, 0)

            # Slot limiti
            over_limit = iso_mrg > slot_limit
            lim_str    = '⚠️ AŞTI' if over_limit else 'OK'

            # ROE renk/ikon
            if roe <= ALERT_ROE:
                roe_str = f"🔴{roe:+.1f}%"
                critical.append(f"🚨 {symbol} {side} ROE={roe:.1f}% — LİKİDASYON RİSKİ!")
            elif roe < -30:
                roe_str = f"🟠{roe:+.1f}%"
            elif roe < 0:
                roe_str = f"🟡{roe:+.1f}%"
            else:
                roe_str = f"🟢{roe:+.1f}%"

            print(f"  {symbol:<12} {side:<6} {lev:>4}x  {roe_str:>10}  {upnl:>+10.2f}$  {iso_mrg:>8.2f}$  {d_lvl:>2}  {tp_lvl:>3}  {lim_str}")

            if over_limit:
                critical.append(f"⚠️ SLOT LİMİTİ AŞILDI: {symbol} {side} margin={iso_mrg:.2f} > limit={slot_limit:.2f}")

        # Kritik uyarılar
        if critical:
            print()
            sep('!', 65)
            for c in critical:
                print(f"  {c}")
            sep('!', 65)

        # Toplam PnL
        total_upnl = sum(float(p['unRealizedProfit']) for p in open_pos)
        print(f"\n  Toplam Unrealized PnL: {total_upnl:+.2f} USDT")

    except Exception as e:
        print(f"❌ Rapor hatası: {e}")

    sep('═')

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print('═' * 65)
    print('  MİNA v2 — SİSTEM MONİTOR')
    print(f'  Başlatıldı: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}')
    print(f'  Log: {LOG_FILE}')
    print(f'  Rapor aralığı: {REPORT_INTERVAL}s | ROE uyarı: {ALERT_ROE}%')
    print('═' * 65)
    print('Log eventi geldiğinde anında basılacak.')
    print('Her 5 dakikada tam rapor verilecek.\n')

    config = BinanceConfig()
    client = config.get_client()

    # Log başlangıç pozisyonu
    try:
        last_pos = os.path.getsize(LOG_FILE)
    except:
        last_pos = 0

    last_report = 0  # hemen ilk raporu ver

    while True:
        try:
            # Log satırlarını kontrol et
            last_pos, alerts = watch_log(LOG_FILE, last_pos)

            # 5 dakikada bir tam rapor
            if time.time() - last_report >= REPORT_INTERVAL:
                full_report(client)
                last_report = time.time()

            time.sleep(5)

        except KeyboardInterrupt:
            print(f"\n{ts()} Monitor durduruldu.")
            break
        except Exception as e:
            print(f"\n{ts()} ❌ Monitor hatası: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
