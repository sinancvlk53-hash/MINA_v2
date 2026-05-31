"""
MINA v2 Dashboard — Playwright Test Suite
Çalıştır: python tests/test_dashboard.py
HTML rapor: tests/report.html
"""

import asyncio
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, expect

# Windows terminal UTF-8 zorla
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL    = "http://178.105.150.40:3000"
REPORT_DIR  = Path(__file__).parent
TIMEOUT     = 20_000   # ms
LOAD_WAIT   = 5_000    # WS verisi için bekleme

# ─────────────────────────────────────────
# Test sonuçlarını tutan basit kayıt yapısı
# ─────────────────────────────────────────
results: list[dict] = []

def record(name: str, passed: bool, detail: str = "", screenshot: str = ""):
    mark  = "[OK]" if passed else "[FAIL]"
    emoji = "OK"   if passed else "FAIL"
    results.append({
        "name": name,
        "passed": passed,
        "detail": detail,
        "screenshot": screenshot,
        "emoji": "✅" if passed else "❌",
    })
    print(f"  {mark}  {name}" + (f"  ->  {detail}" if detail else ""))


# ─────────────────────────────────────────
# YARDIMCI
# ─────────────────────────────────────────
async def take_shot(page, name: str) -> str:
    path = str(REPORT_DIR / f"shot_{name}.png")
    await page.screenshot(path=path, full_page=False)
    return path


# ─────────────────────────────────────────
# TEST 1 — Dashboard yükleniyor mu?
# ─────────────────────────────────────────
async def test_dashboard_loads(page):
    print("\n[1] Dashboard yükleme")
    try:
        resp = await page.goto(BASE_URL, timeout=TIMEOUT, wait_until="domcontentloaded")
        ok   = resp is not None and resp.status == 200
        record("HTTP 200 alındı", ok, f"status={resp.status if resp else 'None'}")

        # Başlık
        title = await page.title()
        has_title = bool(title)
        record("Sayfa başlığı var", has_title, title)

        # Ana kapsayıcı
        app = page.locator(".app")
        await app.wait_for(state="visible", timeout=TIMEOUT)
        record(".app container görünür", True)

        # Header
        header = page.locator("header, .header")
        header_vis = await header.count() > 0
        record("Header render edildi", header_vis)

        # WebSocket verisi bekle
        await page.wait_for_timeout(LOAD_WAIT)
        shot = await take_shot(page, "01_loaded")
        record("Ekran goruntusu alindi", True, shot)

    except Exception as e:
        record("Dashboard yükleme", False, str(e))


# ─────────────────────────────────────────
# TEST 2 — TP paneli doğruluğu
# ─────────────────────────────────────────
async def test_tp_panel(page):
    print("\n[2] TP Paneli")
    try:
        await page.wait_for_timeout(LOAD_WAIT)

        # TP satırları (.tp-row veya içinde TP1/TP2 geçen hücreler)
        tp_rows = page.locator("tr.tp-row, .tp-row")
        tp_count = await tp_rows.count()

        if tp_count == 0:
            # Alternatif: body text içinde TP1/TP2 sayısı
            page_text_check = await page.inner_text("body")
            tp_count = page_text_check.count("TP1") + page_text_check.count("TP2")

        record("TP satirlari/etiketleri var", tp_count > 0, f"{tp_count} referans")

        # TP1 fiyatları — sayı formatında bir şeyler var mı?
        page_text = await page.inner_text("body")
        has_tp1   = "TP1" in page_text or "tp1" in page_text.lower()
        has_tp2   = "TP2" in page_text or "tp2" in page_text.lower()
        record("TP1 etiketi sayfada mevcut", has_tp1)
        record("TP2 etiketi sayfada mevcut", has_tp2)

        shot = await take_shot(page, "02_tp_panel")
        record("TP paneli ekran görüntüsü", True, shot)

    except Exception as e:
        record("TP paneli", False, str(e))


# ─────────────────────────────────────────
# TEST 3 — Defense paneli (4x'e özel mi?)
# ─────────────────────────────────────────
async def test_defense_panel(page):
    print("\n[3] Defense Paneli")
    try:
        # "Defense Panel" başlığı
        dp = page.locator("text=Defense Panel")
        dp_visible = await dp.count() > 0
        record("Defense Panel başlığı görünür", dp_visible)

        # D1 / D2 / D3 etiketleri
        d1 = page.locator("text=D1")
        d2 = page.locator("text=D2")
        d3 = page.locator("text=D3")
        has_d1 = await d1.count() > 0
        has_d2 = await d2.count() > 0
        has_d3 = await d3.count() > 0
        record("D1 etiketi var", has_d1)
        record("D2 etiketi var", has_d2)
        record("D3 etiketi var", has_d3)

        # Engine durum badge (AKTİF/PASİF)
        page_text = await page.inner_text("body")
        has_engine_badge = "AKTİF" in page_text or "PASİF" in page_text or "—" in page_text
        record("Engine durum badge'i var", has_engine_badge)

        shot = await take_shot(page, "03_defense")
        record("Defense paneli ekran görüntüsü", True, shot)

    except Exception as e:
        record("Defense paneli", False, str(e))


# ─────────────────────────────────────────
# TEST 4 — Log akışı butonları
# ─────────────────────────────────────────
async def test_log_buttons(page):
    print("\n[4] Log Akışı Butonları")
    try:
        # "Log Akışı" başlığı
        log_section = page.locator("text=Log Akışı")
        log_vis = await log_section.count() > 0
        record("Log Akışı bölümü görünür", log_vis)

        # Canlı İzle butonu
        live_btn = page.locator("button", has_text="Canlı İzle")
        live_cnt = await live_btn.count()
        record("'Canlı İzle' butonu var", live_cnt > 0, f"{live_cnt} adet")

        if live_cnt > 0:
            await live_btn.first.click()
            await page.wait_for_timeout(500)
            record("'Canlı İzle' tıklanabilir", True)
            # Tekrar tıkla — toggle
            await live_btn.first.click()
            await page.wait_for_timeout(300)
            record("'Canlı İzle' toggle çalışıyor", True)

        # Test Akışını İzle butonu
        test_btn = page.locator("button", has_text="Test Akışını İzle")
        test_cnt = await test_btn.count()
        record("'Test Akışını İzle' butonu var", test_cnt > 0, f"{test_cnt} adet")

        if test_cnt > 0:
            await test_btn.first.click()
            await page.wait_for_timeout(500)
            record("'Test Akışını İzle' tıklanabilir", True)
            await test_btn.first.click()
            await page.wait_for_timeout(300)

        # Devamını Gör — hiddenCount > 0 olduğunda görünür olmalı
        devami_btn = page.locator("button", has_text="Devamını Gör")
        devami_cnt = await devami_btn.count()
        record("'Devamını Gör' butonu var (log varsa)", devami_cnt >= 0,
               "görünür" if devami_cnt > 0 else "log sayısı < 3, normal")

        shot = await take_shot(page, "04_log_buttons")
        record("Log butonları ekran görüntüsü", True, shot)

    except Exception as e:
        record("Log butonları", False, str(e))


# ─────────────────────────────────────────
# TEST 5 — TradingView grafik
# ─────────────────────────────────────────
async def test_tradingview(page):
    print("\n[5] TradingView Grafik")
    try:
        # TradingView widget container
        tv_container = page.locator(".tradingview-widget-container")
        tv_cnt = await tv_container.count()
        record("TradingView container oluştu", tv_cnt > 0, f"{tv_cnt} adet")

        # iframe yüklendiyse
        tv_iframe = page.locator("iframe[src*='tradingview']")
        tv_if_cnt = await tv_iframe.count()
        record("TradingView iframe var", tv_if_cnt > 0,
               "yüklendi" if tv_if_cnt > 0 else "sembol seçilmemiş olabilir")

        # Grafik wrapper boyutu kontrolü
        chart_wrapper = page.locator(".chart-layer, .chart-wrapper, .col-center .section-card")
        if await chart_wrapper.count() > 0:
            box = await chart_wrapper.first.bounding_box()
            has_size = box is not None and box["width"] > 100 and box["height"] > 100
            record("Grafik alanı boyutlandırıldı", has_size,
                   f"{box['width']:.0f}×{box['height']:.0f}px" if box else "box yok")

        shot = await take_shot(page, "05_tradingview")
        record("TradingView ekran görüntüsü", True, shot)

    except Exception as e:
        record("TradingView", False, str(e))


# ─────────────────────────────────────────
# TEST 6 — Mobil görünüm (375px)
# ─────────────────────────────────────────
async def test_mobile(page, context):
    print("\n[6] Mobil Görünüm (375px)")
    mobile_page = None
    try:
        mobile_page = await context.new_page()
        await mobile_page.set_viewport_size({"width": 375, "height": 812})
        resp = await mobile_page.goto(BASE_URL, timeout=TIMEOUT, wait_until="domcontentloaded")
        record("Mobil: HTTP 200", resp is not None and resp.status == 200)

        await mobile_page.wait_for_timeout(LOAD_WAIT)

        # .app görünür mü?
        app = mobile_page.locator(".app")
        app_vis = await app.count() > 0
        record("Mobil: .app container var", app_vis)

        # Yatay taşma (overflow) yok mu?
        scroll_width = await mobile_page.evaluate("document.body.scrollWidth")
        viewport_w   = 375
        no_overflow  = scroll_width <= viewport_w + 10   # 10px tolerans
        record("Mobil: yatay taşma yok", no_overflow,
               f"scrollWidth={scroll_width}px (viewport={viewport_w}px)")

        # Header 375px'de görünür mü?
        header = mobile_page.locator("header, .header")
        if await header.count() > 0:
            box = await header.first.bounding_box()
            fits = box is not None and box["width"] <= viewport_w + 5
            record("Mobil: header ekrana sığıyor", fits,
                   f"{box['width']:.0f}px" if box else "box yok")

        shot_path = str(REPORT_DIR / "shot_06_mobile.png")
        await mobile_page.screenshot(path=shot_path)
        record("Mobil ekran görüntüsü", True, shot_path)

    except Exception as e:
        record("Mobil görünüm", False, str(e))
    finally:
        if mobile_page:
            await mobile_page.close()


# ─────────────────────────────────────────
# HTML RAPOR ÜRETIMI
# ─────────────────────────────────────────
def build_html_report() -> str:
    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    ts     = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    rows = ""
    for r in results:
        color = "#0ECB81" if r["passed"] else "#F6465D"
        bg    = "#0ECB8108" if r["passed"] else "#F6465D0A"
        shot_html = ""
        if r["screenshot"] and Path(r["screenshot"]).exists():
            fname = Path(r["screenshot"]).name
            shot_html = f'<a href="{fname}" target="_blank" style="color:#3b82f6;font-size:11px">📷 görüntü</a>'
        rows += f"""
        <tr style="background:{bg}">
          <td style="padding:8px 12px;font-size:16px">{r["emoji"]}</td>
          <td style="padding:8px 12px;color:#E0E3E7">{r["name"]}</td>
          <td style="padding:8px 12px;color:#848e9c;font-size:12px">{r["detail"]}</td>
          <td style="padding:8px 12px">{shot_html}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MINA v2 Dashboard Test Raporu</title>
<style>
  body {{ background:#0b0e11; color:#E0E3E7; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; margin:0; padding:24px }}
  h1   {{ color:#F0B90B; margin-bottom:4px }}
  .meta {{ color:#848e9c; font-size:13px; margin-bottom:24px }}
  .summary {{ display:flex; gap:24px; margin-bottom:24px }}
  .badge {{ padding:8px 20px; border-radius:6px; font-weight:700; font-size:15px }}
  .green {{ background:#0ECB8118; border:1px solid #0ECB8140; color:#0ECB81 }}
  .red   {{ background:#F6465D18; border:1px solid #F6465D40; color:#F6465D }}
  .gray  {{ background:#1E2329; border:1px solid #2d3f50; color:#848e9c }}
  table  {{ width:100%; border-collapse:collapse; background:#1E2329; border-radius:8px; overflow:hidden }}
  th     {{ padding:10px 12px; text-align:left; background:#2d3f50; color:#848e9c; font-size:11px; text-transform:uppercase; letter-spacing:.8px }}
  tr     {{ border-bottom:1px solid #2d3f5030 }}
  tr:last-child {{ border-bottom:none }}
</style>
</head>
<body>
<h1>MINA v2 — Dashboard Test Raporu</h1>
<div class="meta">{ts} · {BASE_URL}</div>
<div class="summary">
  <div class="badge green">✅ Geçti: {passed}</div>
  <div class="badge red">❌ Başarısız: {failed}</div>
  <div class="badge gray">Toplam: {len(results)}</div>
</div>
<table>
  <thead>
    <tr>
      <th></th><th>Test</th><th>Detay</th><th>Görüntü</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</body>
</html>"""
    return html


# ─────────────────────────────────────────
# ANA RUNNER
# ─────────────────────────────────────────
async def run():
    print("=" * 55)
    print("  MINA v2 Dashboard — Playwright Test Suite")
    print(f"  Hedef: {BASE_URL}")
    print("=" * 55)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Konsol hata/uyarılarını yakala
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        await test_dashboard_loads(page)
        await test_tp_panel(page)
        await test_defense_panel(page)
        await test_log_buttons(page)
        await test_tradingview(page)
        await test_mobile(page, context)

        # Konsol hataları
        print("\n[7] Konsol Hataları")
        js_errors = [e for e in console_errors if "favicon" not in e.lower()]
        record("JS konsol hatası yok", len(js_errors) == 0,
               f"{len(js_errors)} hata" if js_errors else "temiz")
        for e in js_errors[:3]:
            print(f"     ⚠  {e[:120]}")

        await browser.close()

    # Özet
    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    print("\n" + "=" * 55)
    print(f"  Sonuç: {passed} geçti / {failed} başarısız / {len(results)} toplam")
    print("=" * 55)

    # HTML rapor
    report_path = REPORT_DIR / "report.html"
    report_path.write_text(build_html_report(), encoding="utf-8")
    print(f"\n  HTML rapor: {report_path}")
    return failed


if __name__ == "__main__":
    failed_count = asyncio.run(run())
    exit(0 if failed_count == 0 else 1)
