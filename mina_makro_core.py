# -*- coding: utf-8 -*-
"""MINA Makro İzleyici — piyasa rejimi, skor, alarm, Telegram."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = os.environ.get("MINA_DATA_ROOT", os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "signal_bot", "makro_watcher_state.json")
NEWS_STATE_PATH = os.path.join(ROOT, "signal_bot", "news_watcher_state.json")
WATCH_INTERVAL_SEC = int(os.environ.get("MAKRO_WATCH_SEC", str(15 * 60)))

TR_TZ = timezone(timedelta(hours=3))
FAPI = "https://fapi.binance.com"
COINGECKO_GLOBAL = "https://api.coingecko.com/api/v3/global"
FNG_URL = "https://api.alternative.me/fng/?limit=1"

STABLE_KEYS = ("usdt", "usdc", "dai", "busd", "tusd", "usdd", "fdusd")

# alarm_key -> cooldown saniye
ALARM_COOLDOWNS = {
    "funding_high": 4 * 3600,
    "funding_low": 4 * 3600,
    "oi_spike": 4 * 3600,
    "ls_extreme": 4 * 3600,
    "fear_greed": 6 * 3600,
    "btc_d": 4 * 3600,
    "usdt_d": 4 * 3600,
    "total_crash": 3 * 3600,
    "dxy_spike": 6 * 3600,
    "oil_drop": 6 * 3600,
    "spx_drop": 6 * 3600,
    "gold_spike": 6 * 3600,
    "combo": 2 * 3600,
}

METRIC_KEYS = [
    "TOTAL", "TOTAL2", "TOTAL3", "OTHERS",
    "BTC.D", "USDT.D", "ETH.D",
    "BTC", "ETH", "ETH_BTC",
    "BTC_FUNDING", "ETH_FUNDING",
    "BTC_OI", "BTC_LS",
    "XAU", "FEAR_GREED", "DXY", "USOIL", "SPX",
]


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _http_get(url: str, params: Optional[dict] = None, timeout: int = 15) -> Any:
    r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": "MINA-makro/1.0"})
    r.raise_for_status()
    return r.json()


def _metric(value: Any, change: Optional[float] = None, unit: str = "", display: Optional[str] = None) -> dict:
    direction = "flat"
    if change is not None:
        if change > 0.05:
            direction = "up"
        elif change < -0.05:
            direction = "down"
    return {
        "value": value,
        "change24h": change,
        "direction": direction,
        "unit": unit,
        "display": display,
    }


def _fetch_binance_ticker(symbol: str) -> Tuple[Optional[float], Optional[float]]:
    try:
        row = _http_get(f"{FAPI}/fapi/v1/ticker/24hr", {"symbol": symbol})
        price = float(row.get("lastPrice") or 0)
        chg = float(row.get("priceChangePercent") or 0)
        return price, chg
    except Exception:
        return None, None


def _fetch_binance_funding(symbol: str) -> Optional[float]:
    try:
        rows = _http_get(f"{FAPI}/fapi/v1/fundingRate", {"symbol": symbol, "limit": 1})
        if rows:
            return float(rows[0].get("fundingRate") or 0) * 100.0
    except Exception:
        pass
    return None


def _fetch_binance_oi(symbol: str) -> Optional[float]:
    try:
        row = _http_get(f"{FAPI}/fapi/v1/openInterest", {"symbol": symbol})
        return float(row.get("openInterest") or 0)
    except Exception:
        return None


def _fetch_binance_ls(symbol: str) -> Optional[float]:
    try:
        rows = _http_get(
            f"{FAPI}/futures/data/globalLongShortAccountRatio",
            {"symbol": symbol, "period": "5m", "limit": 1},
        )
        if rows:
            return float(rows[0].get("longShortRatio") or 0)
    except Exception:
        pass
    return None


def _fetch_coingecko() -> Tuple[dict, str]:
    status = "ok"
    out: Dict[str, Any] = {}
    try:
        payload = _http_get(COINGECKO_GLOBAL)
        g = payload.get("data") or {}
        total = float(str(g.get("total_market_cap", {}).get("usd", 0)).replace(",", ""))
        chg = float(g.get("market_cap_change_percentage_24h_usd") or 0)
        pct = g.get("market_cap_percentage") or {}

        btc_pct = float(pct.get("btc") or 0)
        eth_pct = float(pct.get("eth") or 0)
        usdt_pct = float(pct.get("usdt") or 0)
        stable_pct = sum(float(pct.get(k) or 0) for k in STABLE_KEYS)

        btc_cap = total * btc_pct / 100.0
        eth_cap = total * eth_pct / 100.0
        stable_cap = total * stable_pct / 100.0
        others_b = max(0.0, total - btc_cap - eth_cap - stable_cap) / 1e9

        out["TOTAL"] = _metric(round(total / 1e12, 4), chg, "T", f"{total / 1e12:.3f}T")
        out["TOTAL2"] = _metric(round((total - btc_cap) / 1e12, 4), None, "T")
        out["TOTAL3"] = _metric(round((total - btc_cap - eth_cap) / 1e12, 4), None, "T")
        out["OTHERS"] = _metric(round(others_b, 2), None, "B", f"{others_b:.1f}B")
        out["BTC.D"] = _metric(round(btc_pct, 3), None, "%", f"{btc_pct:.2f}%")
        out["USDT.D"] = _metric(round(usdt_pct, 3), None, "%", f"{usdt_pct:.2f}%")
        out["ETH.D"] = _metric(round(eth_pct, 3), None, "%", f"{eth_pct:.2f}%")
    except Exception as exc:
        status = f"err: {exc}"
    return out, status


def _fetch_fear_greed() -> Tuple[Optional[dict], str]:
    try:
        payload = _http_get(FNG_URL)
        row = (payload.get("data") or [{}])[0]
        val = int(row.get("value") or 0)
        label = str(row.get("value_classification") or "")
        return _metric(val, None, "", f"{val} ({label})"), "ok"
    except Exception as exc:
        return None, f"err: {exc}"


def _fetch_yfinance(symbol: str) -> Tuple[Optional[dict], str]:
    try:
        import yfinance as yf

        t = yf.Ticker(symbol)
        hist = t.history(period="5d")
        if hist.empty:
            return None, "no_data"
        last = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last
        chg = ((last - prev) / prev * 100.0) if prev else 0.0
        disp = f"{last:.2f}" if last < 1000 else f"{last:,.0f}"
        return _metric(round(last, 4), round(chg, 3), "", disp), "ok"
    except Exception as exc:
        return None, f"err: {exc}"


def _fetch_xau() -> Tuple[Optional[dict], str]:
    try:
        row = _http_get(f"{FAPI}/fapi/v1/premiumIndex", {"symbol": "XAUUSDT"})
        price = float(row.get("markPrice") or 0)
        if price <= 0:
            return None, "skip"
        return _metric(round(price, 2), None, "$", f"${price:,.0f}"), "ok"
    except Exception:
        return None, "skip"


def fetch_all_metrics(prev: dict) -> Tuple[dict, dict]:
    """Tüm metrikleri çek; kaynak sağlığını döndür."""
    metrics: Dict[str, dict] = {}
    sources: Dict[str, str] = {}

    cg, cg_st = _fetch_coingecko()
    sources["coingecko"] = cg_st
    metrics.update(cg)

    btc_p, btc_chg = _fetch_binance_ticker("BTCUSDT")
    eth_p, eth_chg = _fetch_binance_ticker("ETHUSDT")
    sources["binance_ticker"] = "ok" if btc_p else "err"

    if btc_p:
        metrics["BTC"] = _metric(btc_p, btc_chg, "$", f"${btc_p:,.0f}")
    if eth_p:
        metrics["ETH"] = _metric(eth_p, eth_chg, "$", f"${eth_p:,.0f}")

    eth_btc_p, eth_btc_chg = _fetch_binance_ticker("ETHBTC")
    if eth_btc_p:
        metrics["ETH_BTC"] = _metric(eth_btc_p, eth_btc_chg, "", f"{eth_btc_p:.6f}")

    btc_fund = _fetch_binance_funding("BTCUSDT")
    eth_fund = _fetch_binance_funding("ETHUSDT")
    sources["binance_funding"] = "ok" if btc_fund is not None else "err"
    if btc_fund is not None:
        metrics["BTC_FUNDING"] = _metric(round(btc_fund, 4), None, "%", f"{btc_fund:+.4f}%")
    if eth_fund is not None:
        metrics["ETH_FUNDING"] = _metric(round(eth_fund, 4), None, "%", f"{eth_fund:+.4f}%")

    oi = _fetch_binance_oi("BTCUSDT")
    sources["binance_oi"] = "ok" if oi else "err"
    if oi:
        prev_oi = (prev.get("metrics") or {}).get("BTC_OI", {}).get("value")
        oi_chg = None
        if prev_oi and prev_oi > 0:
            oi_chg = round((oi - prev_oi) / prev_oi * 100.0, 3)
        metrics["BTC_OI"] = _metric(round(oi, 2), oi_chg, "BTC", f"{oi:,.0f}")

    ls = _fetch_binance_ls("BTCUSDT")
    sources["binance_ls"] = "ok" if ls else "err"
    if ls:
        metrics["BTC_LS"] = _metric(round(ls, 3), None, "", f"{ls:.2f}")

    xau, xau_st = _fetch_xau()
    sources["xau"] = xau_st
    if xau:
        metrics["XAU"] = xau

    fg, fg_st = _fetch_fear_greed()
    sources["fear_greed"] = fg_st
    if fg:
        metrics["FEAR_GREED"] = fg

    dxy, dxy_st = _fetch_yfinance("DX-Y.NYB")
    sources["dxy"] = dxy_st
    if dxy:
        metrics["DXY"] = dxy

    oil, oil_st = _fetch_yfinance("CL=F")
    sources["usoil"] = oil_st
    if oil:
        metrics["USOIL"] = oil

    spx, spx_st = _fetch_yfinance("^GSPC")
    sources["spx"] = spx_st
    if spx:
        metrics["SPX"] = spx

    # Önceki değerleri koru (kaynak çöktüyse)
    prev_metrics = prev.get("metrics") or {}
    for key in METRIC_KEYS:
        if key not in metrics and key in prev_metrics:
            old = dict(prev_metrics[key])
            old["stale"] = True
            metrics[key] = old

    # Dominans / OI gibi metriklerde önceki döngüye göre yön hesapla
    for key, cur in metrics.items():
        if cur.get("change24h") is not None:
            continue
        old_val = (prev_metrics.get(key) or {}).get("value")
        new_val = cur.get("value")
        if old_val is not None and new_val is not None and old_val != 0:
            pct = round((new_val - old_val) / abs(old_val) * 100.0, 4)
            cur["change24h"] = pct
            if pct > 0.05:
                cur["direction"] = "up"
            elif pct < -0.05:
                cur["direction"] = "down"
            else:
                cur["direction"] = "flat"

    return metrics, sources


def _trend(metric: dict, key: str = "change24h", threshold: float = 0.1) -> str:
    chg = metric.get(key)
    if chg is None:
        chg = metric.get("change24h")
    if chg is None:
        return "flat"
    if chg > threshold:
        return "up"
    if chg < -threshold:
        return "down"
    return "flat"


def analyze_combinations(metrics: dict) -> List[str]:
    combos: List[str] = []
    m = metrics

    fund = (m.get("BTC_FUNDING") or {}).get("value") or 0
    oi_dir = _trend(m.get("BTC_OI") or {}, "change24h", 0.5)
    btc_dir = _trend(m.get("BTC") or {})
    btc_d_dir = _trend(m.get("BTC.D") or {}, "change24h", 0.05)
    total_dir = _trend(m.get("TOTAL") or {})
    eth_btc_dir = _trend(m.get("ETH_BTC") or {})
    usdt_d_dir = _trend(m.get("USDT.D") or {}, "change24h", 0.02)
    dxy_dir = _trend(m.get("DXY") or {})
    others_dir = _trend(m.get("OTHERS") or {}, "change24h", 0.3)
    oil_dir = _trend(m.get("USOIL") or {})
    spx_dir = _trend(m.get("SPX") or {})

    if fund >= 0.03 and oi_dir == "up" and btc_dir == "up":
        combos.append("Aşırı long — funding yüksek, OI artıyor, fiyat yükseliyor → düşüş riski")

    if btc_d_dir == "down" and total_dir == "up" and eth_btc_dir == "up":
        combos.append("Altcoin sezonu — BTC.D düşüyor, TOTAL ve ETH/BTC yükseliyor")

    if usdt_d_dir == "up" and total_dir == "down" and dxy_dir == "up":
        combos.append("Risk-off — USDT.D ve DXY yükseliyor, TOTAL düşüyor → nakde kaçış")

    if others_dir == "up" and btc_d_dir == "down":
        combos.append("Altcoin sezonu güçleniyor — OTHERS yükseliyor, BTC.D düşüyor")

    if oil_dir == "down" and dxy_dir == "up" and spx_dir == "down":
        combos.append("Küresel risk-off — petrol, hisse düşüyor, DXY yükseliyor → kripto tehlikede")

    if fund <= -0.01 and btc_dir == "down":
        combos.append("Aşırı short baskısı — negatif funding + BTC zayıf")

    fg = (m.get("FEAR_GREED") or {}).get("value")
    if fg is not None and fg <= 20 and total_dir == "down":
        combos.append("Aşırı korku + piyasa düşüşü — savunmacı mod")

    if fg is not None and fg >= 80 and fund >= 0.05:
        combos.append("Aşırı açgözlülük + yüksek funding — balon riski")

    return combos


def compute_scores(metrics: dict, combos: List[str]) -> Tuple[int, int]:
    """Risk skoru 0-6 (yüksek=sağlıklı), Macro skoru -100..+100."""
    health = 0
    macro = 0.0

    fg = (metrics.get("FEAR_GREED") or {}).get("value")
    if fg is not None:
        if 35 <= fg <= 65:
            health += 1
            macro += 8
        elif fg < 25:
            macro -= 12
        elif fg > 75:
            macro -= 8

    fund = (metrics.get("BTC_FUNDING") or {}).get("value") or 0
    if -0.01 <= fund <= 0.03:
        health += 1
        macro += 5
    elif fund > 0.05:
        macro -= 22
    elif fund > 0.03:
        macro -= 12
    elif fund < -0.02:
        macro -= 8

    oi_chg = (metrics.get("BTC_OI") or {}).get("change24h")
    if oi_chg is not None:
        if oi_chg > 3 and fund > 0.02:
            macro -= 18
        elif -2 <= oi_chg <= 2:
            health += 1

    ls = (metrics.get("BTC_LS") or {}).get("value")
    if ls is not None:
        if 0.9 <= ls <= 1.3:
            health += 1
            macro += 4
        elif ls > 1.8:
            macro -= 10
        elif ls < 0.7:
            macro -= 6

    total_chg = (metrics.get("TOTAL") or {}).get("change24h")
    if total_chg is not None:
        if total_chg > 0:
            macro += 10
        elif total_chg < -3:
            macro -= 15
        else:
            health += 1

    btc_d_chg = (metrics.get("BTC.D") or {}).get("change24h")
    if btc_d_chg is not None:
        if btc_d_chg < -0.1:
            macro += 8
        elif btc_d_chg > 0.15:
            macro -= 6

    eth_btc_chg = (metrics.get("ETH_BTC") or {}).get("change24h")
    if eth_btc_chg is not None:
        macro += max(-10, min(10, eth_btc_chg * 3))

    usdt_d_chg = (metrics.get("USDT.D") or {}).get("change24h")
    if usdt_d_chg is not None and usdt_d_chg > 0.05:
        macro -= 10

    dxy_chg = (metrics.get("DXY") or {}).get("change24h")
    if dxy_chg is not None:
        macro -= dxy_chg * 2

    xau_chg = (metrics.get("XAU") or {}).get("change24h")
    if xau_chg is not None and xau_chg > 1:
        macro -= 4

    spx_chg = (metrics.get("SPX") or {}).get("change24h")
    if spx_chg is not None:
        macro += spx_chg * 1.5

    oil_chg = (metrics.get("USOIL") or {}).get("change24h")
    if oil_chg is not None:
        macro += oil_chg * 0.8

    for c in combos:
        if "risk-off" in c.lower() or "düşüş riski" in c.lower() or "tehlikede" in c.lower():
            macro -= 8
        elif "altcoin sezonu" in c.lower():
            macro += 6

    health = max(0, min(6, health))
    macro = max(-100, min(100, round(macro)))
    return health, macro


def _load_news_risk() -> dict:
    """news_watcher_state.json → son haber risk snapshot."""
    try:
        state = _read_json(NEWS_STATE_PATH, {})
        return state.get("last_result") or {}
    except Exception:
        return {}


def compute_weighted_score(metrics: dict) -> int:
    """
    Ağırlıklı makro iklim puanı — 0 (iyi) ile 10 (kötü) arası.
    Düşük puan = piyasa sağlıklı = giriş uygun.
    """
    score = 5.0  # başlangıç nötr

    def _chg(key: str, alt_key: str = "") -> float:
        row = metrics.get(key) or (metrics.get(alt_key) if alt_key else {}) or {}
        v = row.get("change_pct", row.get("change24h", 0))
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    def _val(key: str, default: float = 0) -> float:
        row = metrics.get(key) or {}
        v = row.get("value", default)
        try:
            return float(v if v is not None else default)
        except (TypeError, ValueError):
            return default

    # Fear & Greed (%30 ağırlık)
    fg = _val("FEAR_GREED", 50)
    if fg <= 20:
        score += 1.5   # aşırı korku = riskli
    elif fg <= 35:
        score += 0.75
    elif fg >= 75:
        score -= 1.5   # açgözlülük = fırsat biter
    elif fg >= 60:
        score -= 0.75

    # BTC.D (%25 ağırlık)
    btcd_chg = _chg("BTC.D", "BTC_D")
    if btcd_chg > 0.3:
        score += 1.25   # BTC dominant → altcoin riski
    elif btcd_chg < -0.3:
        score -= 1.25  # altcoin sezonu

    # TOTAL trend (%20 ağırlık)
    total_chg = _chg("TOTAL")
    if total_chg < -3:
        score += 1.0   # piyasa düşüşte
    elif total_chg < -1:
        score += 0.5
    elif total_chg > 2:
        score -= 1.0   # piyasa yükseliyor
    elif total_chg > 0:
        score -= 0.5

    # Funding Rate (%15 ağırlık)
    funding = _val("BTC_FUNDING", 0)
    if funding > 0.05:
        score += 0.75  # aşırı long pozisyon
    elif funding < -0.01:
        score += 0.375  # aşırı short
    elif 0 <= funding <= 0.02:
        score -= 0.375  # sağlıklı

    # DXY (%10 ağırlık)
    dxy_chg = _chg("DXY")
    if dxy_chg > 0.5:
        score += 0.5   # dolar güçleniyor = kripto riski
    elif dxy_chg < -0.5:
        score -= 0.5

    # Haber risk skoru (news_watcher — makro döngüsünde güncellenir)
    news = _load_news_risk()
    news_score = int(news.get("score", 0) or 0)
    if news.get("alert") or news_score >= 9:
        score += 2.5
    elif news_score >= 7:
        score += 1.0
    elif news_score >= 6:
        score += 0.5
    elif news_score <= 2 and int(news.get("fetched", 0) or 0) > 0:
        score -= 0.25

    # 0-10 arası sınırla
    return max(0, min(10, round(score)))


def trade_permission(macro_score: int) -> Tuple[str, str]:
    if macro_score >= 30:
        return "FULL_RISK", "🟢 FULL RISK"
    if macro_score <= -30:
        return "DEFENSIVE", "🔴 DİKKAT"
    return "REDUCED_RISK", "🟡 RİSKLİ"


def detect_alarms(metrics: dict, combos: List[str]) -> List[Tuple[str, str]]:
    """(alarm_key, mesaj) listesi."""
    alarms: List[Tuple[str, str]] = []
    m = metrics

    fund = (m.get("BTC_FUNDING") or {}).get("value")
    if fund is not None:
        if fund >= 0.05:
            alarms.append(("funding_high", f"BTC funding aşırı yüksek: {fund:+.4f}%"))
        elif fund <= -0.03:
            alarms.append(("funding_low", f"BTC funding aşırı negatif: {fund:+.4f}%"))

    oi_chg = (m.get("BTC_OI") or {}).get("change24h")
    if oi_chg is not None and oi_chg > 5:
        alarms.append(("oi_spike", f"BTC Open Interest +%{oi_chg:.1f} artış"))

    ls = (m.get("BTC_LS") or {}).get("value")
    if ls is not None:
        if ls > 1.8:
            alarms.append(("ls_extreme", f"BTC Long/Short oranı yüksek: {ls:.2f}"))
        elif ls < 0.65:
            alarms.append(("ls_extreme", f"BTC Long/Short oranı düşük: {ls:.2f}"))

    fg = (m.get("FEAR_GREED") or {}).get("value")
    if fg is not None and (fg <= 15 or fg >= 85):
        alarms.append(("fear_greed", f"Fear & Greed aşırı: {fg}"))

    btc_d = (m.get("BTC.D") or {}).get("value")
    if btc_d is not None and (btc_d >= 60 or btc_d <= 48):
        alarms.append(("btc_d", f"BTC.D uç değer: {btc_d:.2f}%"))

    usdt_d = (m.get("USDT.D") or {}).get("value")
    if usdt_d is not None and usdt_d >= 8:
        alarms.append(("usdt_d", f"USDT.D yüksek: {usdt_d:.2f}% — nakde kaçış"))

    total_chg = (m.get("TOTAL") or {}).get("change24h")
    if total_chg is not None and total_chg <= -4:
        alarms.append(("total_crash", f"TOTAL günlük %{total_chg:.1f} düşüş"))

    dxy_chg = (m.get("DXY") or {}).get("change24h")
    if dxy_chg is not None and dxy_chg >= 0.8:
        alarms.append(("dxy_spike", f"DXY güçleniyor: +%{dxy_chg:.2f}"))

    oil_chg = (m.get("USOIL") or {}).get("change24h")
    if oil_chg is not None and oil_chg <= -3:
        alarms.append(("oil_drop", f"Petrol düşüyor (%{oil_chg:.1f}) — küresel risk iştahı azalıyor"))

    spx_chg = (m.get("SPX") or {}).get("change24h")
    if spx_chg is not None and spx_chg <= -2:
        alarms.append(("spx_drop", f"S&P500 düşüyor (%{spx_chg:.1f}) — kripto dikkat"))

    for combo in combos:
        if any(k in combo.lower() for k in ("risk-off", "düşüş riski", "tehlikede", "savunmacı")):
            alarms.append(("combo", combo))

    return alarms


def _cooldown_ok(state: dict, key: str) -> bool:
    cooldowns = state.get("alarm_cooldowns") or {}
    last = cooldowns.get(key, 0)
    cd = ALARM_COOLDOWNS.get(key, 3600)
    return time.time() - float(last) >= cd


def _mark_cooldown(state: dict, key: str) -> None:
    cooldowns = state.setdefault("alarm_cooldowns", {})
    cooldowns[key] = time.time()


def send_telegram(text: str) -> bool:
    try:
        from tools.telegram_bot import send_notification
        return bool(send_notification(text))
    except Exception as exc:
        print(f"[MAKRO] Telegram hatası: {exc}")
        return False


def _format_metric_line(key: str, m: dict) -> str:
    disp = m.get("display") or m.get("value")
    chg = m.get("change24h")
    arrow = "→"
    if m.get("direction") == "up":
        arrow = "↑"
    elif m.get("direction") == "down":
        arrow = "↓"
    stale = " (eski)" if m.get("stale") else ""
    chg_s = f" ({chg:+.2f}%)" if chg is not None else ""
    return f"• {key}: {disp}{chg_s} {arrow}{stale}"


def build_morning_summary(state: dict) -> str:
    m = state.get("metrics") or {}
    risk = state.get("risk_score", 0)
    macro = state.get("macro_score", 0)
    perm = state.get("trade_permission_label", "—")
    combos = state.get("combinations") or []
    sources = state.get("sources") or {}

    lines = [
        "🌐 *MINA Makro Sabah Özeti*",
        f"_{datetime.now(TR_TZ).strftime('%Y-%m-%d %H:%M')} TR_",
        "",
        f"*İşlem İzni:* {perm}",
        f"*Risk Skoru:* {risk}/6  |  *Macro Skor:* {macro:+d}",
        "",
        "*Piyasa Verileri:*",
    ]
    for key in METRIC_KEYS:
        if key in m:
            lines.append(_format_metric_line(key, m[key]))

    if combos:
        lines.append("")
        lines.append("*Kombinasyon Analizi:*")
        for c in combos[:5]:
            lines.append(f"• {c}")

    ok_src = [k for k, v in sources.items() if v == "ok"]
    bad_src = [f"{k}={v}" for k, v in sources.items() if v != "ok"]
    lines.append("")
    lines.append(f"*Kaynaklar:* {len(ok_src)} ok" + (f" | sorun: {', '.join(bad_src)}" if bad_src else ""))

    return "\n".join(lines)


def watcher_cycle() -> dict:
    prev = _read_json(STATE_PATH, {})
    first_run = not prev.get("metrics")

    try:
        from signal_bot.news_watcher import run_news_watcher
        run_news_watcher()
        print("[MAKRO] Haber taraması tamamlandı")
    except Exception as e:
        print(f"[MAKRO] Haber tarama hatası: {e}")

    metrics, sources = fetch_all_metrics(prev)
    combos = analyze_combinations(metrics)
    risk_score, macro_score = compute_scores(metrics, combos)
    perm_key, perm_label = trade_permission(macro_score)

    now = datetime.now(TR_TZ)
    state = {
        "updated_at": now.isoformat(),
        "metrics": metrics,
        "combinations": combos,
        "risk_score": risk_score,
        "macro_score": macro_score,
        "trade_permission": perm_key,
        "trade_permission_label": perm_label,
        "sources": sources,
        "alarm_cooldowns": prev.get("alarm_cooldowns") or {},
        "last_morning_summary": prev.get("last_morning_summary"),
    }

    _write_json(STATE_PATH, state)

    if first_run:
        print("[MAKRO] İlk çalıştırma — alarm yok, baseline kaydedildi")
        return state

    # Anlık alarmlar (cooldown'lı, birleşik)
    alarms = detect_alarms(metrics, combos)
    to_send: List[str] = []
    for key, msg in alarms:
        if _cooldown_ok(state, key):
            to_send.append(msg)
            _mark_cooldown(state, key)

    if to_send:
        body = "⚠️ *Makro Alarm*\n" + "\n".join(f"• {x}" for x in to_send)
        send_telegram(body)
        _write_json(STATE_PATH, state)

    # Sabah 08:00 özeti (TR)
    today = now.date().isoformat()
    if now.hour == 8 and now.minute < 16 and state.get("last_morning_summary") != today:
        send_telegram(build_morning_summary(state))
        state["last_morning_summary"] = today
        _write_json(STATE_PATH, state)
        print("[MAKRO] Sabah özeti gönderildi")

    print(
        f"[MAKRO] risk={risk_score}/6 macro={macro_score:+d} {perm_label} "
        f"combos={len(combos)} sources_ok={sum(1 for v in sources.values() if v == 'ok')}"
    )
    return state


def load_dashboard_payload() -> dict:
    """Dashboard WS için snapshot."""
    state = _read_json(STATE_PATH, {})
    if not state:
        return {
            "metrics": {},
            "riskScore": 0,
            "macroScore": 0,
            "macroWeightedScore": 5,
            "macroWeightedLabel": "⚠️ DİKKATLİ",
            "tradePermission": "REDUCED_RISK",
            "tradePermissionLabel": "🟡 RİSKLİ",
            "combinations": [],
            "sources": {},
            "updatedAt": None,
            "stale": True,
        }
    metrics = state.get("metrics") or {}
    weighted_score = compute_weighted_score(metrics)
    return {
        "metrics": metrics,
        "riskScore": state.get("risk_score", 0),
        "macroScore": state.get("macro_score", 0),
        "macroWeightedScore": weighted_score,
        "macroWeightedLabel": (
            "✅ UYGUN" if weighted_score <= 3 else
            "⚠️ DİKKATLİ" if weighted_score <= 6 else
            "🚨 RİSKLİ"
        ),
        "tradePermission": state.get("trade_permission", "REDUCED_RISK"),
        "tradePermissionLabel": state.get("trade_permission_label", "🟡 RİSKLİ"),
        "combinations": state.get("combinations") or [],
        "sources": state.get("sources") or {},
        "updatedAt": state.get("updated_at"),
        "stale": False,
    }
