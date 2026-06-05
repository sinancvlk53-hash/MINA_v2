# -*- coding: utf-8 -*-
"""MINA v2 — 10 slot dağılım politikası (anayasa)."""

SLOT_TOTAL = 10

# Merter 1x DCA (3 slot)
SLOTS_EI_DCA = 2
SLOTS_MERTER_OTHER_DCA = 1
MERTER_DCA_YUVAS = (
    "merter_ei_1",
    "merter_ei_2",
    "merter_other",
)
EI_YUVAS = ("merter_ei_1", "merter_ei_2")

# 4x motor (7 slot — Haluk Hoca pipeline)
SLOTS_HALUK_MOTOR = 7
SLOTS_MERTER_MOTOR = 1
MOTOR_SLOT_MAX = SLOTS_HALUK_MOTOR + SLOTS_MERTER_MOTOR  # 8

# Geriye dönük alias (eski state dosyaları)
LEGACY_YUVA_MAP = {
    "merter_ei": "merter_ei_1",
    "merter_rsi": "merter_other",
}

MERTER_DCA_LABELS = {
    "merter_ei_1": "EI #1 — Süzgeçli",
    "merter_ei_2": "EI #2 — Süzgeçsiz",
    "merter_other": "Merter Diğer (RSI)",
}

MERTER_DCA_FILTER_MODE = {
    "merter_ei_1": "filtered",
    "merter_ei_2": "unfiltered",
    "merter_other": "rsi",
}

MERTER_DCA_FILTER_DESC = {
    "merter_ei_1": "RVOL≥2 + EMA20 + SFP + hacim + pump koruması",
    "merter_ei_2": "Filtre yok — EI listesinden doğrudan giriş",
    "merter_other": "RSI<20 + teyit + hacim",
}
