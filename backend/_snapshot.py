# -*- coding: utf-8 -*-
"""Anlık pozisyon snapshot + log özeti
Tracking dosyaları (initial_margins, defense_levels, tp_levels) ve
log her zaman SUNUCUDAN (178.105.150.40) canlı okunur — stale local data yok.
"""
import sys, os, json, io
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BinanceConfig
from datetime import datetime

# ── Sunucu bağlantısı ──────────────────────────────────────────────────
SERVER_HOST = '178.105.150.40'
SERVER_USER = 'root'
SERVER_PASS = 'REDACTED'
REMOTE_ROOT = '/root/MINA_v2'

ALERT_ROE   = -70.0

def _ssh_client():
    import paramiko
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER_HOST, username=SERVER_USER, password=SERVER_PASS, timeout=10)
    return c

def remote_json(sftp, filename: str) -> dict:
    """Sunucudan JSON dosyasını oku, hata varsa {} döndür."""
    try:
        buf = io.BytesIO()
        sftp.getfo(f'{REMOTE_ROOT}/{filename}', buf)
        return json.loads(buf.getvalue().decode('utf-8'))
    except Exception:
        return {}

def remote_log_summary(ssh) -> dict:
    """Sunucudaki mina_bot.log dosyasından event sayılarını çek."""
    events = {'D1': 0, 'D2': 0, 'D3_ok': 0, 'D3_fail': 0,
              'TP1': 0, 'TP2': 0, 'SL': 0, 'TRAILING': 0, 'ERR': 0}
    cmds = {
        'D1':       "grep -c 'SAVUNMA 1.*eklendi'",
        'D2':       "grep -c 'SAVUNMA 2.*eklendi'",
        'D3_ok':    "grep -c 'SAVUNMA 3.*MARGIN eklendi'",
        'D3_fail':  "grep -cE 'SAVUNMA 3.*(BAŞARISIZ|HATASI|MARGIN HATASI)'",
        'TP1':      "grep -c '💰 TP1:'",
        'TP2':      "grep -c '💰 TP2:'",
        'TRAILING': "grep -c 'TRAILING.*kapatıldı'",
        'SL':       "grep -c 'STOP LOSS.*kapatıldı'",
        'ERR':      "grep -cE 'ERROR|KRİTİK HATA'",
    }
    log = f'{REMOTE_ROOT}/mina_bot.log'
    for key, cmd in cmds.items():
        _, out, _ = ssh.exec_command(f'{cmd} {log} 2>/dev/null || echo 0')
        try:
            events[key] = int(out.read().decode().strip())
        except Exception:
            events[key] = 0
    return events

def remote_last_log_lines(ssh, n: int = 10) -> list[str]:
    """Sunucudan son N log satırını çek."""
    _, out, _ = ssh.exec_command(f'tail -n {n} {REMOTE_ROOT}/mina_bot.log 2>/dev/null')
    return [l.rstrip() for l in out.read().decode('utf-8', errors='replace').splitlines()]

# ── Bağlantı kur ───────────────────────────────────────────────────────
print('═'*65, flush=True)
print(f'  MİNA v2 — ANLIKKK RAPOR  {datetime.now().strftime("%H:%M:%S")}', flush=True)
print('═'*65, flush=True)

try:
    ssh  = _ssh_client()
    sftp = ssh.open_sftp()
    print(f'  [SSH] {SERVER_HOST} baglantisi OK', flush=True)
except Exception as e:
    print(f'  [SSH] BAGLANTI HATASI: {e}', flush=True)
    sys.exit(1)

# ── LOG ÖZETİ (sunucudan) ───────────────────────────────────────────────
events = remote_log_summary(ssh)
print('\n📋 LOG ÖZETI (sunucu log, tüm oturumlar):', flush=True)
print(f'   D1 tetiklemeler  : {events["D1"]}',      flush=True)
print(f'   D2 tetiklemeler  : {events["D2"]}',      flush=True)
print(f'   D3 BAŞARILI      : {events["D3_ok"]}',   flush=True)
print(f'   D3 BAŞARISIZ     : {events["D3_fail"]}', flush=True)
print(f'   TP1 tetiklemeler : {events["TP1"]}',     flush=True)
print(f'   TP2 tetiklemeler : {events["TP2"]}',     flush=True)
print(f'   TRAILING kapatma : {events["TRAILING"]}',flush=True)
print(f'   SL tetiklemeler  : {events["SL"]}',      flush=True)
print(f'   Hatalar          : {events["ERR"]}',     flush=True)

# ── TRACKING DOSYALARI (sunucudan canlı) ───────────────────────────────
defense_lvls = remote_json(sftp, 'defense_levels.json')
init_margins = remote_json(sftp, 'initial_margins.json')
tp_lvls      = remote_json(sftp, 'tp_levels.json')
iep          = remote_json(sftp, 'initial_entry_prices.json')

sftp.close()

# ── BİNANCE POZİSYONLARI ───────────────────────────────────────────────
config   = BinanceConfig()
client   = config.get_client()

bal_data  = client.futures_account_balance()
balance   = float(next(x for x in bal_data if x['asset'] == 'USDT')['balance'])
slot_size = balance / 10

positions = client.futures_position_information()
open_pos  = [p for p in positions if float(p['positionAmt']) != 0]

print(f'\n💰 Bakiye: {balance:.2f} USDT  |  Slot: {slot_size:.2f} USDT', flush=True)
print(f'📊 Açık Pozisyon: {len(open_pos)}\n', flush=True)

print(f'  {"Coin":<12} {"Side":<6} {"Lev":>4}  {"ROE":>9}  {"PnL":>10}  '
      f'{"IsoMrj":>7}  {"D":>2}  {"TP":>3}  {"D2 Mesafe":>10}  {"Uyarı"}', flush=True)
print(f'  {"─"*12} {"─"*6} {"─"*4}  {"─"*9}  {"─"*10}  '
      f'{"─"*7}  {"─"*2}  {"─"*3}  {"─"*10}  {"─"*12}', flush=True)

warnings = []
for p in open_pos:
    symbol  = p['symbol']
    side    = 'LONG' if float(p['positionAmt']) > 0 else 'SHORT'
    lev     = int(p['leverage'])
    upnl    = float(p['unRealizedProfit'])
    iso_mrg = float(p['isolatedMargin'])
    mark    = float(p['markPrice'])
    liq     = float(p['liquidationPrice'])
    pos_key = f'{symbol}_{side}'

    # init_margin: sunucudan gelen gerçek değer (D1 sonrası güncel)
    init_m  = init_margins.get(pos_key, iso_mrg)
    roe     = (upnl / init_m * 100) if init_m > 0 else 0.0
    d_lvl   = defense_lvls.get(pos_key, 0)
    tp_lvl  = tp_lvls.get(pos_key, 0)

    # D2 tetikleyici mesafesi (fiyat bazlı)
    init_ep = iep.get(pos_key)
    if init_ep:
        if side == 'LONG':
            d2_px  = init_ep * 0.88
            d2_gap = (mark - d2_px) / d2_px * 100
        else:
            d2_px  = init_ep * 1.12
            d2_gap = (d2_px - mark) / d2_px * 100
        d2_str = f'{d2_gap:+.1f}%' if d2_gap > 0 else f'GECİLDİ!'
    else:
        d2_str = '—'

    # Uyarı mantığı
    warn = ''
    liq_dist = abs((mark - liq) / liq * 100) if liq > 0 else 999
    if roe <= ALERT_ROE:
        warn = '🔴ROE ALARM'
        warnings.append(f'🚨 {symbol} {side} ROE={roe:.1f}%  liq_dist={liq_dist:.1f}%')
    if liq_dist < 15:
        warn = '🔴LİK ALARM'
        warnings.append(f'🚨 {symbol} {side} likidasyon {liq_dist:.1f}% uzakta (liq={liq:.6g})')
    elif iso_mrg > slot_size * 1.02:
        warn = '⚠️ LİMİT'

    roe_icon = ('🟢' if roe >= 0
                else '🔴' if roe <= ALERT_ROE
                else '🟠' if roe < -30
                else '🟡')

    print(f'  {symbol:<12} {side:<6} {lev:>4}x  '
          f'{roe_icon}{roe:>+7.2f}%  {upnl:>+10.2f}$  '
          f'{iso_mrg:>7.2f}$  {d_lvl:>2}  {tp_lvl!s:>3}  '
          f'{d2_str:>10}  {warn}', flush=True)

total = sum(float(p['unRealizedProfit']) for p in open_pos)
print(f'\n  Toplam PnL: {total:+.2f} USDT', flush=True)

if warnings:
    print('\n' + '!'*65, flush=True)
    for w in warnings: print(f'  {w}', flush=True)
    print('!'*65, flush=True)

# ── SON LOG SATIRLARI (sunucudan) ───────────────────────────────────────
print('\n📝 SON 10 LOG SATIRI (sunucu):', flush=True)
for line in remote_last_log_lines(ssh, 10):
    print(f'   {line}', flush=True)

ssh.close()
print('\n' + '═'*65, flush=True)
