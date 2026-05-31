# -*- coding: utf-8 -*-
"""
MinaPositionManager
═══════════════════
MINA Algoritmik Ticaret Sistemi — Pozisyon ve Savunma Motoru
ANAYASA: TECHNICAL_SPECIFICATION_AND_COMPLIANCE_MANDATE_V2

Kapsam:
  • BudgetSpec          – Kasa / slot bütçe anayasası (frozen, değiştirilemez)
  • DefenseSpec         – D1/D2/D3 tetik oranları ve ortalama sabitleri (frozen)
  • SlotPosition        – Tek slot'un durumunu tutan veri yapısı
  • MinaPositionManager – Tüm iş mantığını barındıran ana yönetici sınıf
  • run_simulation()    – 1 000 USDT kasa ile örnek senaryo çalıştırıcı
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MINA")

# ──────────────────────────────────────────────────────────────────────────────
# EVRENSEL SABİTLER  (anayasadan alınmıştır — değiştirilemez)
# ──────────────────────────────────────────────────────────────────────────────
BINANCE_FEE_MULTIPLIER = 1.0012   # Arkalı önlü Binance komisyonu (round-trip)
LIQUIDATION_RATIO      = 0.75     # D3 sonrası hard stop: initial_entry × 0.75


# ──────────────────────────────────────────────────────────────────────────────
# ENUM'LAR
# ──────────────────────────────────────────────────────────────────────────────
class DefenseLevel(Enum):
    NONE = 0
    D1   = 1
    D2   = 2
    D3   = 3


class PositionState(Enum):
    OPEN             = "OPEN"
    CLOSED_TP1_BE    = "CLOSED_TP1_BE"      # TP1 sonrası başabaşa düştü
    CLOSED_TRAILING  = "CLOSED_TRAILING"    # Trailing stop
    CLOSED_BREAKEVEN = "CLOSED_BREAKEVEN"   # D2/D3 başabaş stop
    CLOSED_HARD_STOP = "CLOSED_HARD_STOP"   # EP × 0.75 hard stop
    CLOSED_MANUAL    = "CLOSED_MANUAL"


# ──────────────────────────────────────────────────────────────────────────────
# BÜTÇE ANAYASASI  (frozen — tek satır değişmez)
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class BudgetSpec:
    """
    MINA Bütçe Anayasası
    ─────────────────────
    Örnek Kasa: 1 000 USDT / 10 Slot / 4x Isolated LONG

    Slot dağılımı (100 USDT = 5 eşit parça × 20 USDT):
      Giriş  : slot × 0.20 =  20 USDT → 4x →  80 USDT notional
      D1     : slot × 0.20 =  20 USDT → 4x →  80 USDT notional
      D2     : slot × 0.20 =  20 USDT → 4x →  80 USDT notional
      D3     : slot × 0.40 =  40 USDT → 4x → 160 USDT notional
      Toplam :               100 USDT → 4x → 400 USDT notional
    """
    total_capital : float = 1_000.0
    slot_count    : int   = 10
    leverage      : int   = 4

    # ── Türetilmiş değerler ────────────────────────────────────────────────
    @property
    def slot_size(self) -> float:
        return self.total_capital / self.slot_count          # 100 USDT

    @property
    def entry_margin(self) -> float:
        return self.slot_size * 0.20                         # 20 USDT

    @property
    def d1_margin(self) -> float:
        return self.slot_size * 0.20                         # 20 USDT

    @property
    def d2_margin(self) -> float:
        return self.slot_size * 0.20                         # 20 USDT

    @property
    def d3_margin(self) -> float:
        return self.slot_size * 0.40                         # 40 USDT

    @property
    def total_committed(self) -> float:
        return self.slot_size                                # 100 USDT

    @property
    def entry_notional(self) -> float:
        return self.entry_margin * self.leverage             #  80 USDT

    @property
    def d1_notional(self) -> float:
        return self.d1_margin * self.leverage                #  80 USDT

    @property
    def d2_notional(self) -> float:
        return self.d2_margin * self.leverage                #  80 USDT

    @property
    def d3_notional(self) -> float:
        return self.d3_margin * self.leverage                # 160 USDT

    @property
    def total_notional(self) -> float:
        return self.total_committed * self.leverage          # 400 USDT

    def print_budget_table(self) -> None:
        SEP = "═" * 66
        sep = "─" * 66
        logger.info(SEP)
        logger.info(f"  💰  MINA BÜTÇE ANAYASASI — {self.total_capital:,.2f} USDT KASA")
        logger.info(SEP)
        logger.info(f"  {'Parametreler':<30}")
        logger.info(f"  Toplam Kasa     : {self.total_capital:>10,.2f} USDT")
        logger.info(f"  Slot Sayısı     : {self.slot_count:>10} adet")
        logger.info(f"  Slot Büyüklüğü  : {self.slot_size:>10.2f} USDT")
        logger.info(f"  Kaldıraç / Mod  : {self.leverage:>10}x  Isolated LONG")
        logger.info(sep)
        logger.info(f"  {'Kademe':<22} {'Marj':>10} {'Oran':>6} {'Notional':>12}")
        logger.info(f"  {'-'*22} {'-'*10} {'-'*6} {'-'*12}")
        rows = [
            ("Giriş (Initial Entry)", self.entry_margin, "20%", self.entry_notional),
            ("D1  Savunma",           self.d1_margin,    "20%", self.d1_notional),
            ("D2  Savunma",           self.d2_margin,    "20%", self.d2_notional),
            ("D3  Son Kale",          self.d3_margin,    "40%", self.d3_notional),
        ]
        for label, margin, pct, notional in rows:
            logger.info(f"  {label:<22} {margin:>8.2f} $ {pct:>5}  {notional:>10.2f} $")
        logger.info(f"  {'-'*22} {'-'*10} {'-'*6} {'-'*12}")
        logger.info(f"  {'TOPLAM':<22} {self.total_committed:>8.2f} $ {'100%':>5}  {self.total_notional:>10.2f} $")
        logger.info(SEP)


# ──────────────────────────────────────────────────────────────────────────────
# SAVUNMA ANAYASASI  (frozen — tek satır değişmez)
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class DefenseSpec:
    """
    ANAYASA §3 — Defans Motoru Sabitleri
    ──────────────────────────────────────
    D1 : initial_entry_price × 0.95  →  -%5  → 20 USDT kontrat alımı
    D2 : initial_entry_price × 0.88  →  -%12 → 20 USDT kontrat alımı
         Yeni Ort  = initial_entry × 0.9434
         be_price  = yeni_ort     × 1.0012  →  Binance TAKE_PROFIT_MARKET
    D3 : SFP (Hayalet — Dinamik Price Action)  → 40 USDT kontrat alımı
         Yeni Ort  = initial_entry × 0.8817
         be_price  = yeni_ort     × 1.0012  →  Binance TAKE_PROFIT_MARKET
         Hard Stop = initial_entry × 0.75   →  -%25 likidasyon limiti
    """
    d1_trigger_ratio  : float = 0.9500   # EP × 0.95
    d2_trigger_ratio  : float = 0.8800   # EP × 0.88

    d2_avg_ratio      : float = 0.9434   # Giriş+D1+D2 sonrası ağırlıklı ortalama (anayasa)
    d3_avg_ratio      : float = 0.8817   # Giriş+D1+D2+D3 sonrası ağırlıklı ortalama (anayasa)

    liquidation_ratio : float = LIQUIDATION_RATIO   # 0.75

    # be_ratio'lar post_init'te türetilir
    d2_be_ratio       : float = field(init=False)
    d3_be_ratio       : float = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "d2_be_ratio", self.d2_avg_ratio * BINANCE_FEE_MULTIPLIER)
        object.__setattr__(self, "d3_be_ratio", self.d3_avg_ratio * BINANCE_FEE_MULTIPLIER)

    # ── Fiyat hesaplayıcılar ───────────────────────────────────────────────
    def d1_trigger(self, ep: float) -> float:
        return ep * self.d1_trigger_ratio

    def d2_trigger(self, ep: float) -> float:
        return ep * self.d2_trigger_ratio

    def d2_avg(self, ep: float) -> float:
        return ep * self.d2_avg_ratio

    def d2_be(self, ep: float) -> float:
        return ep * self.d2_be_ratio

    def d3_avg(self, ep: float) -> float:
        return ep * self.d3_avg_ratio

    def d3_be(self, ep: float) -> float:
        return ep * self.d3_be_ratio

    def hard_liq(self, ep: float) -> float:
        return ep * self.liquidation_ratio

    def print_defense_table(self, ep: float) -> None:
        sep = "─" * 66
        logger.info(sep)
        logger.info(f"  🛡️   SAVUNMA PROTOKOLÜ  (EP = {ep:,.4f} USDT)")
        logger.info(sep)
        logger.info(f"  {'Kademe':<18} {'Oran':>8} {'Fiyat':>14} {'Açıklama'}")
        logger.info(f"  {'-'*18} {'-'*8} {'-'*14} {'-'*18}")
        rows = [
            ("D1 Tetik",   f"×{self.d1_trigger_ratio}", self.d1_trigger(ep), "-%5  → 20 USDT kontrat"),
            ("D2 Tetik",   f"×{self.d2_trigger_ratio}", self.d2_trigger(ep), "-%12 → 20 USDT kontrat"),
            ("D2 Ortalama",f"×{self.d2_avg_ratio}",     self.d2_avg(ep),     "Giriş+D1+D2 ağırlıklı"),
            ("D2 Başabaş", f"×{self.d2_be_ratio:.6f}",  self.d2_be(ep),      "Ort × 1.0012 → STOP EMRİ"),
            ("D3 Tetik",   "SFP",                        0.0,                 "Dinamik — Price Action"),
            ("D3 Ortalama",f"×{self.d3_avg_ratio}",     self.d3_avg(ep),     "Giriş+D1+D2+D3 ağırlıklı"),
            ("D3 Başabaş", f"×{self.d3_be_ratio:.6f}",  self.d3_be(ep),      "Ort × 1.0012 → STOP EMRİ"),
            ("Hard Stop",  f"×{self.liquidation_ratio}", self.hard_liq(ep),   "Likidasyon limiti -%25"),
        ]
        for label, ratio, price, desc in rows:
            price_str = f"{price:>12.4f} $" if price > 0 else f"{'—':>12}"
            logger.info(f"  {label:<18} {ratio:>8} {price_str}  {desc}")
        logger.info(sep)


# ──────────────────────────────────────────────────────────────────────────────
# TEK SLOT POZİSYON — VERİ YAPISI
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class SlotPosition:
    symbol              : str
    initial_entry_price : float
    open_time           : datetime = field(default_factory=datetime.now)

    # Mevcut durum
    defense_level       : DefenseLevel  = DefenseLevel.NONE
    state               : PositionState = PositionState.OPEN
    tp_level            : int           = 0      # 0 → TP1 bekleniyor, 1 → TP2 / trailing
    trailing_active     : bool          = False
    trailing_high       : float         = 0.0    # TP1 sonrası görülen maksimum fiyat

    # Gerçekleşen dolum fiyatları
    d1_fill_price       : Optional[float] = None
    d2_fill_price       : Optional[float] = None
    d3_fill_price       : Optional[float] = None

    # Aktif Binance stop emri (D2/D3 başabaş)
    active_be_order_id  : Optional[str]   = None

    # Anlık fiyat (tick güncellemesi)
    _current_price      : float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._current_price = self.initial_entry_price

    @property
    def current_price(self) -> float:
        return self._current_price

    @current_price.setter
    def current_price(self, v: float) -> None:
        self._current_price = v

    @property
    def price_change_pct(self) -> float:
        """Anlık fiyat değişimi % (kaldıraçsız)"""
        ep = self.initial_entry_price
        return ((self._current_price - ep) / ep) * 100

    def is_closed(self) -> bool:
        return self.state != PositionState.OPEN


# ──────────────────────────────────────────────────────────────────────────────
# ANA YÖNETİCİ
# ──────────────────────────────────────────────────────────────────────────────
class MinaPositionManager:
    """
    MINA Algoritmik Ticaret Sistemi — Pozisyon Yöneticisi
    ANAYASA: TECHNICAL_SPECIFICATION_AND_COMPLIANCE_MANDATE_V2

    Kullanım:
        mgr = MinaPositionManager(total_capital=1_000.0)
        pos = mgr.open_position("BTCUSDT", entry_price=100_000.0)
        result = mgr.on_price_tick(pos, current_price=95_000.0)

    sfp_detector imzası:
        def my_sfp_detector(symbol: str, current_price: float) -> dict:
            # TradingView API + major support analizi burada yapılır
            return {
                "sfp_confirmed"  : bool,    # SFP teyit edildi mi?
                "major_support"  : float,   # 4H/1D major destek çizgisi
                "wick_low"       : float,   # İğne ucu (order block dip)
                "confirm_tf"     : str,     # Teyit mumu zaman dilimi (1m/5m)
                "confirm_close"  : float,   # Teyit mumu kapanış fiyatı
            }
    """

    def __init__(
        self,
        total_capital   : float              = 1_000.0,
        leverage        : int                = 4,
        tp1_pct         : float              = 3.0,    # TP1 eşiği (%)
        tp2_pct         : float              = 5.0,    # TP2 eşiği (%)
        tp1_close_frac  : float              = 0.50,   # TP1'de kapatılacak oran
        tp2_close_frac  : float              = 0.50,   # Kalan pozisyondan TP2'de kapat
        trailing_pct    : float              = 1.0,    # Tepeden geri çekilme eşiği (%)
        sfp_detector    : Optional[Callable] = None,   # D3 SFP algılayıcısı
    ) -> None:
        self.budget         = BudgetSpec(total_capital=total_capital, leverage=leverage)
        self.defense        = DefenseSpec()
        self.tp1_pct        = tp1_pct
        self.tp2_pct        = tp2_pct
        self.tp1_close_frac = tp1_close_frac
        self.tp2_close_frac = tp2_close_frac
        self.trailing_pct   = trailing_pct / 100.0
        self.sfp_detector   = sfp_detector

        self.budget.print_budget_table()

    # ──────────────────────────────────────────────────────────────────────────
    # POZİSYON AÇMA
    # ──────────────────────────────────────────────────────────────────────────
    def open_position(self, symbol: str, entry_price: float) -> SlotPosition:
        """
        Yeni pozisyon açar: Initial Entry → slot × 0.20 = 20 USDT marj.
        """
        pos      = SlotPosition(symbol=symbol, initial_entry_price=entry_price)
        ep       = entry_price
        notional = self.budget.entry_notional
        qty      = notional / ep

        SEP = "═" * 66
        sep = "─" * 66
        logger.info(SEP)
        logger.info(f"  📈  POZİSYON AÇILDI — {symbol}  |  {self.budget.leverage}x Isolated LONG")
        logger.info(SEP)
        logger.info(f"  Giriş Fiyatı      : {ep:>14,.4f} USDT")
        logger.info(f"  Marj (Initial)    : {self.budget.entry_margin:>14.2f} USDT  (%20 slot)")
        logger.info(f"  Notional          : {notional:>14.2f} USDT")
        logger.info(f"  Kontrat Adedi     : {qty:>14.6f}")
        logger.info(sep)
        logger.info(f"  TP1 Hedefi        : +{self.tp1_pct:.1f}%  →  {ep*(1+self.tp1_pct/100):>10,.4f} USDT")
        logger.info(f"  TP2 Hedefi        : +{self.tp2_pct:.1f}%  →  {ep*(1+self.tp2_pct/100):>10,.4f} USDT")
        logger.info(sep)
        self.defense.print_defense_table(ep)

        return pos

    # ──────────────────────────────────────────────────────────────────────────
    # ANA FİYAT TICK İŞLEYİCİSİ
    # ──────────────────────────────────────────────────────────────────────────
    def on_price_tick(self, pos: SlotPosition, current_price: float) -> dict[str, Any]:
        """
        Her fiyat güncellemesinde çağrılır.
        İşlem öncelik sırası (ANAYASA §3):
          1. Hard stop limiti   (D3 sonrası EP × 0.75 aşıldıysa)
          2. D1 savunma         (NONE → EP × 0.95 tetiklediyse)
          3. D2 savunma         (D1   → EP × 0.88 tetiklediyse)
          4. D3 SFP             (D2   → Hayalet SFP teyit edildiyse)
          5. D2/D3 başabaş stop (fiyat be_price'e çıkarsa)
          6. TP1 başabaş        (tp_level=1, fiyat EP'e dönerse)
          7. TP/Trailing        (normal kâr alma — D2 modunda askıya alınır)
        """
        if pos.is_closed():
            return {"action": "NONE", "reason": "Pozisyon zaten kapalı"}

        pos.current_price = current_price
        ep                = pos.initial_entry_price
        dl                = pos.defense_level

        # ── 1. Hard Stop (D3 sonrası -%25) ────────────────────────────────
        if dl == DefenseLevel.D3:
            hard_px = self.defense.hard_liq(ep)
            if current_price <= hard_px:
                return self._close(
                    pos, PositionState.CLOSED_HARD_STOP, current_price,
                    f"Hard stop @ {hard_px:.4f} USDT  (EP × 0.75  -%25)",
                )

        # ── 2. D1 Savunma ──────────────────────────────────────────────────
        if dl == DefenseLevel.NONE:
            if current_price <= self.defense.d1_trigger(ep):
                return self._execute_d1(pos, current_price)

        # ── 3. D2 Savunma ──────────────────────────────────────────────────
        if dl == DefenseLevel.D1:
            if current_price <= self.defense.d2_trigger(ep):
                return self._execute_d2(pos, current_price)

        # ── 4. D3 SFP Hayalet Modülü ───────────────────────────────────────
        if dl == DefenseLevel.D2:
            sfp = self._check_d3_sfp(pos, current_price)
            if sfp.get("triggered"):
                return sfp

        # ── 5. D2 / D3 Başabaş Stop ────────────────────────────────────────
        be_result = self._check_be_stop(pos, current_price)
        if be_result["action"] != "NONE":
            return be_result

        # ── 6. TP1 Başabaş (TP1 vuruldu, fiyat EP'e döndü) ────────────────
        if pos.tp_level >= 1 and not pos.trailing_active:
            be_tp1 = ep * BINANCE_FEE_MULTIPLIER
            if current_price <= be_tp1:
                return self._close(
                    pos, PositionState.CLOSED_TP1_BE, current_price,
                    f"TP1 sonrası başabaş stop @ {be_tp1:.4f} USDT",
                )

        # ── 7. TP / Trailing  (D2 BREAKEVEN modunda askıya alınır) ────────
        if dl == DefenseLevel.D2:
            return {"action": "D2_BREAKEVEN_MODE",
                    "be_price": self.defense.d2_be(ep),
                    "current_price": current_price}

        return self._check_tp_and_trailing(pos, current_price)

    # ──────────────────────────────────────────────────────────────────────────
    # SAVUNMA: D1
    # ──────────────────────────────────────────────────────────────────────────
    def _execute_d1(self, pos: SlotPosition, fill_price: float) -> dict[str, Any]:
        pos.defense_level = DefenseLevel.D1
        pos.d1_fill_price = fill_price
        ep                = pos.initial_entry_price
        notional          = self.budget.d1_notional
        qty               = notional / fill_price

        logger.info("─" * 66)
        logger.info(f"  🛡️   SAVUNMA D1 TETİKLENDİ — {pos.symbol}")
        logger.info(f"  Tetik Fiyatı   : {fill_price:>14,.4f} USDT  (EP × 0.95  -%5)")
        logger.info(f"  Marj Alımı     : {self.budget.d1_margin:>14.2f} USDT  (%20 slot)")
        logger.info(f"  Notional       : {notional:>14.2f} USDT")
        logger.info(f"  Kontrat        : {qty:>14.6f}")
        logger.info(f"  Sonraki Tetik  : {self.defense.d2_trigger(ep):>14,.4f} USDT  (EP × 0.88  -%12)")
        logger.info("─" * 66)

        return {
            "action"    : "D1_EXECUTED",
            "fill_price": fill_price,
            "margin"    : self.budget.d1_margin,
            "notional"  : notional,
            "qty"       : qty,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # SAVUNMA: D2
    # ──────────────────────────────────────────────────────────────────────────
    def _execute_d2(self, pos: SlotPosition, fill_price: float) -> dict[str, Any]:
        pos.defense_level = DefenseLevel.D2
        pos.d2_fill_price = fill_price
        ep                = pos.initial_entry_price
        notional          = self.budget.d2_notional
        qty               = notional / fill_price

        avg_price = self.defense.d2_avg(ep)
        be_price  = self.defense.d2_be(ep)
        order_id  = f"D2_STOP_{pos.symbol}_{int(pos.open_time.timestamp())}"
        pos.active_be_order_id = order_id

        SEP = "─" * 66
        logger.info(SEP)
        logger.info(f"  🛡️   SAVUNMA D2 TETİKLENDİ — {pos.symbol}")
        logger.info(f"  Tetik Fiyatı   : {fill_price:>14,.4f} USDT  (EP × 0.88  -%12)")
        logger.info(f"  Marj Alımı     : {self.budget.d2_margin:>14.2f} USDT  (%20 slot)")
        logger.info(f"  Notional       : {notional:>14.2f} USDT")
        logger.info(f"  Kontrat        : {qty:>14.6f}")
        logger.info(SEP)
        logger.info(f"  ── D2 ORTALAMA MALİYET TABLOSU ──────────────────────────")
        logger.info(f"  {'Kademe':<12} {'Fill':>16} {'Notional':>12} {'Oran'}")
        logger.info(f"  {'-'*12} {'-'*16} {'-'*12} {'-'*8}")
        rows_d2 = [
            ("Giriş",  ep * 1.0000, 80.0,  "EP × 1.0000"),
            ("D1",     ep * 0.9500, 80.0,  "EP × 0.9500"),
            ("D2",     fill_price,  80.0,  "EP × 0.8800"),
        ]
        for lbl, fp, nt, ratio in rows_d2:
            logger.info(f"  {lbl:<12} {fp:>14,.4f} $  {nt:>10.2f} $  {ratio}")
        logger.info(f"  {'─'*12} {'─'*16} {'─'*12} {'─'*8}")
        logger.info(f"  {'TOPLAM':<12} {'':>16} {240.0:>10.2f} $")
        logger.info(SEP)
        logger.info(f"  Yeni Ortalama  : {avg_price:>14,.4f} USDT  (EP × 0.9434)")
        logger.info(f"  Başabaş Fiyatı : {be_price:>14,.4f} USDT  (Ort × 1.0012)")
        logger.info(SEP)
        logger.info(f"  BORSA EMRİ → TAKE_PROFIT_MARKET @ {be_price:,.4f} USDT")
        logger.info(f"  Order ID       : {order_id}")
        logger.info(f"  D3 Tetik       : SFP Hayalet — Dinamik Price Action taraması")
        logger.info(SEP)

        return {
            "action"    : "D2_EXECUTED",
            "fill_price": fill_price,
            "margin"    : self.budget.d2_margin,
            "notional"  : notional,
            "qty"       : qty,
            "avg_price" : avg_price,
            "be_price"  : be_price,
            "order_id"  : order_id,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # SAVUNMA: D3 SFP KONTROL
    # ──────────────────────────────────────────────────────────────────────────
    def _check_d3_sfp(self, pos: SlotPosition, current_price: float) -> dict[str, Any]:
        """
        D3 Hayalet SFP Modülü (ANAYASA §3 — [KADEME D3])
        ───────────────────────────────────────────────────
        sfp_detector sağlanmadıysa pasif bekleme modunda kalır;
        borsada önceden limit emir bırakılmaz.

        sfp_detector Koşul Mantığı (harici entegrasyon):
          1. TradingView API → 4H/1D grafiği → major destek / order block wick low tespit
          2. SFP Teyidi:
             a) Fiyat wick_low'un ALTINA anlık iğne atar (likidite temizleme)
             b) 1m/5m mum, major_support çizgisinin ÜSTÜNDE kapanır
          3. Her ikisi EVET → sfp_confirmed = True → D3 çalıştır
        """
        if self.sfp_detector is None:
            return {"triggered": False, "action": "SFP_WATCHING"}

        try:
            signal: dict = self.sfp_detector(pos.symbol, current_price)
        except Exception as exc:
            logger.warning(f"  ⚠️  SFP detector exception: {exc}")
            return {"triggered": False, "action": "SFP_ERROR"}

        if not signal.get("sfp_confirmed", False):
            return {"triggered": False, "action": "SFP_WATCHING"}

        return self._execute_d3(pos, current_price, signal)

    # ──────────────────────────────────────────────────────────────────────────
    # SAVUNMA: D3 ÇALIŞTIRICISI
    # ──────────────────────────────────────────────────────────────────────────
    def _execute_d3(
        self,
        pos         : SlotPosition,
        fill_price  : float,
        sfp_signal  : dict,
    ) -> dict[str, Any]:
        old_order_id      = pos.active_be_order_id
        pos.defense_level = DefenseLevel.D3
        pos.d3_fill_price = fill_price
        ep                = pos.initial_entry_price
        notional          = self.budget.d3_notional
        qty               = notional / fill_price

        avg_price = self.defense.d3_avg(ep)
        be_price  = self.defense.d3_be(ep)
        hard_stop = self.defense.hard_liq(ep)
        order_id  = f"D3_STOP_{pos.symbol}_{int(datetime.now().timestamp())}"
        pos.active_be_order_id = order_id

        SEP = "─" * 66
        logger.info(SEP)
        logger.info(f"  🛡️   SAVUNMA D3 TETİKLENDİ (HAYALET SFP) — {pos.symbol}")
        logger.info(f"  Major Destek   : {sfp_signal.get('major_support', '?'):>14}")
        logger.info(f"  İğne (Wick Low): {sfp_signal.get('wick_low', '?'):>14}")
        logger.info(f"  Teyit TF       : {sfp_signal.get('confirm_tf', '?')}")
        logger.info(f"  Teyit Kapanış  : {sfp_signal.get('confirm_close', '?'):>14}")
        logger.info(f"  Fill Fiyatı    : {fill_price:>14,.4f} USDT  (Market Order)")
        logger.info(f"  Marj Alımı     : {self.budget.d3_margin:>14.2f} USDT  (%40 slot)")
        logger.info(f"  Notional       : {notional:>14.2f} USDT")
        logger.info(f"  Kontrat        : {qty:>14.6f}")
        logger.info(SEP)
        logger.info(f"  ── D3 ORTALAMA MALİYET TABLOSU ──────────────────────────")
        logger.info(f"  {'Kademe':<12} {'Fill':>16} {'Notional':>12} {'Oran'}")
        logger.info(f"  {'-'*12} {'-'*16} {'-'*12} {'-'*8}")
        rows_d3 = [
            ("Giriş",  ep * 1.0000, 80.0,  "EP × 1.0000"),
            ("D1",     ep * 0.9500, 80.0,  "EP × 0.9500"),
            ("D2",     ep * 0.8800, 80.0,  "EP × 0.8800"),
            ("D3",     fill_price,  160.0, "SFP fill"),
        ]
        for lbl, fp, nt, ratio in rows_d3:
            logger.info(f"  {lbl:<12} {fp:>14,.4f} $  {nt:>10.2f} $  {ratio}")
        logger.info(f"  {'─'*12} {'─'*16} {'─'*12} {'─'*8}")
        logger.info(f"  {'TOPLAM':<12} {'':>16} {400.0:>10.2f} $")
        logger.info(SEP)
        logger.info(f"  Yeni Ortalama  : {avg_price:>14,.4f} USDT  (EP × 0.8817)")
        logger.info(f"  Başabaş Fiyatı : {be_price:>14,.4f} USDT  (Ort × 1.0012)")
        logger.info(SEP)
        logger.info(f"  D2 Stop İPTAL  : {old_order_id}")
        logger.info(f"  BORSA EMRİ → TAKE_PROFIT_MARKET @ {be_price:,.4f} USDT")
        logger.info(f"  Order ID       : {order_id}")
        logger.info(f"  Hard Stop Limit: {hard_stop:>14,.4f} USDT  (EP × 0.75  -%25)")
        logger.info(SEP)

        return {
            "triggered"       : True,
            "action"          : "D3_EXECUTED",
            "fill_price"      : fill_price,
            "margin"          : self.budget.d3_margin,
            "notional"        : notional,
            "qty"             : qty,
            "avg_price"       : avg_price,
            "be_price"        : be_price,
            "hard_stop"       : hard_stop,
            "order_id"        : order_id,
            "cancelled_order" : old_order_id,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # BAŞABAŞ STOP KONTROL  (motor yedekleme — Binance emrinin backup'ı)
    # ──────────────────────────────────────────────────────────────────────────
    def _check_be_stop(self, pos: SlotPosition, current_price: float) -> dict[str, Any]:
        """
        LONG pozisyon: fiyat be_price'in ÜSTÜNE çıkarsa kapat.
        D2 → ep × 0.9434 × 1.0012
        D3 → ep × 0.8817 × 1.0012
        """
        ep = pos.initial_entry_price

        if pos.defense_level == DefenseLevel.D2:
            be = self.defense.d2_be(ep)
            if current_price >= be:
                logger.info(f"  ✅ D2 BAŞABAŞ STOP: {current_price:.4f} ≥ {be:.4f}")
                return self._close(
                    pos, PositionState.CLOSED_BREAKEVEN, current_price,
                    f"D2 başabaş stop @ {be:.4f} USDT  (EP × 0.9434 × 1.0012)",
                )

        if pos.defense_level == DefenseLevel.D3:
            be = self.defense.d3_be(ep)
            if current_price >= be:
                logger.info(f"  ✅ D3 BAŞABAŞ STOP: {current_price:.4f} ≥ {be:.4f}")
                return self._close(
                    pos, PositionState.CLOSED_BREAKEVEN, current_price,
                    f"D3 başabaş stop @ {be:.4f} USDT  (EP × 0.8817 × 1.0012)",
                )

        return {"action": "NONE"}

    # ──────────────────────────────────────────────────────────────────────────
    # TP / TAKİPLİ STOP
    # ──────────────────────────────────────────────────────────────────────────
    def _check_tp_and_trailing(
        self, pos: SlotPosition, current_price: float
    ) -> dict[str, Any]:
        ep      = pos.initial_entry_price
        pnl_pct = ((current_price - ep) / ep) * 100

        # ── Trailing aktifse ────────────────────────────────────────────────
        if pos.trailing_active:
            if current_price > pos.trailing_high:
                pos.trailing_high = current_price
            trail_stop = pos.trailing_high * (1.0 - self.trailing_pct)
            if current_price <= trail_stop:
                logger.info(
                    f"  🎯 TRAİLİNG STOP tetiklendi: {current_price:.4f} ≤ "
                    f"{trail_stop:.4f}  (Max: {pos.trailing_high:.4f})"
                )
                return self._close(
                    pos, PositionState.CLOSED_TRAILING, current_price,
                    f"Trailing stop @ {trail_stop:.4f} USDT  "
                    f"(max {pos.trailing_high:.4f} × {1-self.trailing_pct:.2f})",
                )
            return {
                "action"       : "TRAILING_MONITOR",
                "trail_stop"   : trail_stop,
                "trailing_high": pos.trailing_high,
                "pnl_pct"      : pnl_pct,
            }

        # ── TP2 ─────────────────────────────────────────────────────────────
        if pos.tp_level == 1 and pnl_pct >= self.tp2_pct:
            pos.tp_level        = 2
            pos.trailing_active = True
            pos.trailing_high   = current_price
            close_frac          = self.tp2_close_frac
            logger.info(f"  💰 TP2 +{self.tp2_pct:.1f}% @ {current_price:.4f} USDT → "
                        f"Kalan %{close_frac*100:.0f} kapatıldı, Trailing aktif")
            return {
                "action"         : "TP2_HIT",
                "price"          : current_price,
                "pnl_pct"        : pnl_pct,
                "close_frac"     : close_frac,
                "trailing_active": True,
            }

        # ── TP1 ─────────────────────────────────────────────────────────────
        if pos.tp_level == 0 and pnl_pct >= self.tp1_pct:
            pos.tp_level  = 1
            be_price_tp1  = ep * BINANCE_FEE_MULTIPLIER
            close_frac    = self.tp1_close_frac
            logger.info(
                f"  💰 TP1 +{self.tp1_pct:.1f}% @ {current_price:.4f} USDT → "
                f"%{close_frac*100:.0f} kapatıldı, Stop → {be_price_tp1:.4f} USDT"
            )
            return {
                "action"    : "TP1_HIT",
                "price"     : current_price,
                "pnl_pct"   : pnl_pct,
                "close_frac": close_frac,
                "be_price"  : be_price_tp1,
            }

        return {"action": "NONE", "pnl_pct": pnl_pct}

    # ──────────────────────────────────────────────────────────────────────────
    # KAPANIŞ
    # ──────────────────────────────────────────────────────────────────────────
    def _close(
        self,
        pos         : SlotPosition,
        state       : PositionState,
        close_price : float,
        reason      : str,
    ) -> dict[str, Any]:
        pos.state     = state
        ep            = pos.initial_entry_price
        price_chg_pct = ((close_price - ep) / ep) * 100
        roe_pct       = price_chg_pct * self.budget.leverage

        SEP = "═" * 66
        logger.info(SEP)
        logger.info(f"  ✅  POZİSYON KAPANDI — {pos.symbol}  [{state.value}]")
        logger.info(f"  Sebep          : {reason}")
        logger.info(f"  Giriş Fiyatı  : {ep:>14,.4f} USDT")
        logger.info(f"  Kapanış Fiyatı: {close_price:>14,.4f} USDT")
        logger.info(f"  Fiyat Değişimi: {price_chg_pct:>+13.2f}%")
        logger.info(f"  ROE ({self.budget.leverage}x lev.): {roe_pct:>+13.2f}%")
        logger.info(f"  Savunma Kademesi: D{pos.defense_level.value}")
        logger.info(SEP)

        return {
            "action"      : "CLOSED",
            "state"       : state.value,
            "reason"      : reason,
            "close_price" : close_price,
            "price_chg"   : price_chg_pct,
            "roe_pct"     : roe_pct,
        }


# ──────────────────────────────────────────────────────────────────────────────
# SİMÜLASYON — ANAYASA SEKNARYOLARİ
# ──────────────────────────────────────────────────────────────────────────────
def run_simulation() -> None:
    """
    1 000 USDT kasa — BTCUSDT 100 000 USDT giriş fiyatı üzerinden
    3 senaryo simülasyonu:
      A) Normal kâr: TP1 → TP2 → Trailing → Kapanış
      B) D1+D2 savunma → Başabaş çıkış
      C) D1+D2+D3 SFP → Başabaş çıkış
    """
    EP = 100_000.0

    # ──────────────────────────────────────────────────────────────────────
    # SENARYO A: Normal TP Senaryosu
    # ──────────────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("■" * 66)
    logger.info("  SENARYO A — Normal Kâr: TP1 → TP2 → Trailing → Kapanış")
    logger.info("■" * 66)

    mgr_a = MinaPositionManager(total_capital=1_000.0, tp1_pct=3.0, tp2_pct=5.0)
    pos_a = mgr_a.open_position("BTCUSDT", EP)

    for price, label in [
        (EP * 1.03,  "TP1 seviyesi (+3%)"),
        (EP * 1.05,  "TP2 seviyesi (+5%)"),
        (EP * 1.07,  "Yeni zirve (+7%)"),
        (EP * 1.069, "Trailing stop (-%1 tepeden)"),
    ]:
        logger.info(f"\n  → Fiyat: {price:,.2f} USDT  [{label}]")
        result = mgr_a.on_price_tick(pos_a, price)
        logger.info(f"    Aksiyon: {result.get('action')} | "
                    f"PnL: {result.get('pnl_pct', result.get('price_chg', 0)):+.2f}%")

    # ──────────────────────────────────────────────────────────────────────
    # SENARYO B: D1 + D2 Savunma → Başabaş Çıkış
    # ──────────────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("■" * 66)
    logger.info("  SENARYO B — D1 + D2 Savunma → Başabaş Çıkış")
    logger.info("■" * 66)

    mgr_b = MinaPositionManager(total_capital=1_000.0)
    pos_b = mgr_b.open_position("BTCUSDT", EP)

    for price, label in [
        (EP * 0.950, "D1 tetik (-%5)"),
        (EP * 0.880, "D2 tetik (-%12)"),
        (EP * 0.944, "D2 Başabaş Stop seviyesine yakın"),
        (EP * 0.9446,"D2 Başabaş Stop tetiklendi"),
    ]:
        logger.info(f"\n  → Fiyat: {price:,.2f} USDT  [{label}]")
        result = mgr_b.on_price_tick(pos_b, price)
        logger.info(f"    Aksiyon: {result.get('action')}")

    # ──────────────────────────────────────────────────────────────────────
    # SENARYO C: D1 + D2 + D3 SFP → Başabaş Çıkış
    # ──────────────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("■" * 66)
    logger.info("  SENARYO C — D1 + D2 + D3 SFP Hayalet → Başabaş Çıkış")
    logger.info("■" * 66)

    # Mock SFP dedektörü — gerçek entegrasyonda TradingView API kullanılır
    sfp_triggered = False

    def mock_sfp_detector(symbol: str, price: float) -> dict:
        nonlocal sfp_triggered
        major_support = EP * 0.8058
        wick_low      = EP * 0.7950
        if not sfp_triggered and price < wick_low:
            sfp_triggered = True
        if sfp_triggered and price > major_support:
            return {
                "sfp_confirmed" : True,
                "major_support" : f"{major_support:,.4f}",
                "wick_low"      : f"{wick_low:,.4f}",
                "confirm_tf"    : "1m",
                "confirm_close" : f"{price:,.4f}",
            }
        return {"sfp_confirmed": False}

    mgr_c = MinaPositionManager(total_capital=1_000.0, sfp_detector=mock_sfp_detector)
    pos_c = mgr_c.open_position("BTCUSDT", EP)

    for price, label in [
        (EP * 0.950, "D1 tetik (-%5)"),
        (EP * 0.880, "D2 tetik (-%12)"),
        (EP * 0.795, "Wick low altına geçiş (likidite silme)"),
        (EP * 0.810, "SFP teyidi: fiyat major support üstüne kapandı"),
        (EP * 0.882, "D3 Başabaş Stop seviyesi"),
    ]:
        logger.info(f"\n  → Fiyat: {price:,.2f} USDT  [{label}]")
        result = mgr_c.on_price_tick(pos_c, price)
        logger.info(f"    Aksiyon: {result.get('action')}")

    logger.info("")
    logger.info("■" * 66)
    logger.info("  SİMÜLASYON TAMAMLANDI")
    logger.info("■" * 66)


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_simulation()
