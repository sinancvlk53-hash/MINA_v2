import sys
import os
import re
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

import anthropic
import base64

# Haber şalteri — bu ifadeler geçerse otomatik işlem durdurulur
NEWS_ALARM_KEYWORDS = ["FlashCrash", "Mayın Tarlası", "Balina Satışı"]

# UPDATE tuzağı — bu ifadeler geçerse yeni pozisyon açılmaz
UPDATE_TRAP_KEYWORDS = ["UPDATE", "RETEST", "DURUM"]


def _check_filters(text: str) -> dict | None:
    """Metni filtrelerden geçir. Engel varsa blocked dict döner, yoksa None."""
    upper = text.upper()

    for kw in NEWS_ALARM_KEYWORDS:
        if kw.upper() in upper:
            return {"blocked": True, "reason": "haber_alarmi", "keyword": kw}

    for kw in UPDATE_TRAP_KEYWORDS:
        if kw.upper() in upper:
            return {"blocked": True, "reason": "update_mesaji", "keyword": kw}

    return None


def parse_pdf_for_signals(pdf_path: str) -> str:
    """PDF'i Claude ile analiz et, sinyal filtrelerinden geçir, JSON string döndür."""
    with open(pdf_path, 'rb') as f:
        pdf_data = base64.standard_b64encode(f.read()).decode('utf-8')

    client = anthropic.Anthropic()

    # Önce PDF'in ham metnini al (filtre kontrolü için)
    text_msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_data}
                    },
                    {
                        "type": "text",
                        "text": "Bu PDF'in tüm metnini olduğu gibi çıkar. Başka hiçbir şey ekleme."
                    }
                ]
            }
        ]
    )
    raw_text = text_msg.content[0].text

    # Filtre kontrolü
    blocked = _check_filters(raw_text)
    if blocked:
        import json
        return json.dumps([blocked])

    # Filtre geçti — sinyal çıkarımı
    signal_msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_data}
                    },
                    {
                        "type": "text",
                        "text": """Bu PDF bir kripto trading analiz raporu.
Sadece şunları çıkar ve JSON formatında ver:
- coin: sembol (örn: BTCUSDT, XRPUSDT)
- side: LONG veya SHORT
- entry: giriş fiyatı veya bölgesi
- tp1: birinci hedef
- tp2: ikinci hedef (varsa)
- stop: stop loss (varsa)
- leverage: kaldıraç (varsa)

Sadece JSON array döndür, başka hiçbir şey yazma.
Örnek: [{"coin":"BTCUSDT","side":"LONG","entry":"75000","tp1":"78000","tp2":"81000","stop":"72000","leverage":"3x"}]"""
                    }
                ]
            }
        ]
    )

    return signal_msg.content[0].text

if __name__ == '__main__':
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else 'signal_bot/pdfs/last_20260526_060416.pdf'
    result = parse_pdf_for_signals(pdf_path)
    print(result)
