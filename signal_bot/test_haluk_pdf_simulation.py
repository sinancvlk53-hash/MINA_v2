#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Haluk Hoca PDF format simülasyonu — parser sınıflandırma testi.
Gerçek PDF yerine tipik bölüm yapısını metin olarak üretir.
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from signal_bot.haluk_pdf_parser import (
    parse_haluk_document,
    write_raw_signal_queue,
)

SIMULATED_HALUK_REPORT = """
Yatırım Tavsiyesi Değildir. Grafikler eğitim amaçlıdır.

--- SOL ---
SOL analizi — metinde "Pas" ve "şu an değil" yazıyor.
Ancak giriş kutusu ve stop seviyesi tanımlı (grafik kuralı).
Giriş bölgesi: 140.50 - 142.00
Stop: 135.20
Long poz — kutudan sonra girilir denmiş olsa da yapı mevcut.

--- BTC ---
BTC: son omuz için 75'ler gelebilir, oradan dönüş.
Giriş: 75000 - 76000
Stop: 72000
Long — ana senaryo yukarı.

--- TOTAL ---
TOTAL: az daha salarız, kanal dibi gelebilir, ama ana yön yukarı.
Diğer coinlere göre makro filtre — işlem açılmaz.

--- ETH ---
UPDATE: ETH pozisyon durum güncellemesi — RETEST bölgesi.
Bu bölüm yeni sinyal değil, güncelleme mesajıdır.
Giriş: 3200
Stop: 3050
Long devam notu.
"""


def main():
    result = parse_haluk_document(SIMULATED_HALUK_REPORT, source_label="HALUK_SIMULATION")
    queue_path = write_raw_signal_queue(result)

    output = {
        "test": "haluk_pdf_simulation",
        "queue_file": queue_path,
        "system_pause": result.system_pause,
        "macro_filters": result.macro_filters,
        "signals": result.signals,
        "rejected": result.rejected,
        "summary": {
            "approved_signals": len(result.signals),
            "macro_f1_count": len(result.macro_filters),
            "rejected_count": len(result.rejected),
            "sol_leverage": next(
                (s["leverage"] for s in result.signals if s["coin"] == "SOLUSDT"), None
            ),
            "btc_leverage": next(
                (s["leverage"] for s in result.signals if s["coin"] == "BTCUSDT"), None
            ),
            "update_rejected": any(
                r.get("reason") == "update_trap" for r in result.rejected
            ),
        },
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if (
        output["summary"]["approved_signals"] >= 2
        and output["summary"]["macro_f1_count"] >= 1
        and output["summary"]["update_rejected"]
        and output["summary"]["sol_leverage"] == 2
        and output["summary"]["btc_leverage"] == 5
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
