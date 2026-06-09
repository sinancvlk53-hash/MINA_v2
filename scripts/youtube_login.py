#!/usr/bin/env python3
"""YouTube manuel giriş — Playwright cookie kaydı."""
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.firefox.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.youtube.com")

    print("YouTube açıldı.")
    print("Lütfen manuel olarak giriş yapın.")
    print("Giriş tamamlayınca Enter'a basın...")
    input()

    cookies = context.cookies()
    with open("/root/MINA_v2/signal_bot/history/youtube_cookies.json", "w") as f:
        json.dump(cookies, f)

    print("Cookie kaydedildi!")
    browser.close()
