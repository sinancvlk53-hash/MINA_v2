# ✅ MINA Anayasası — Kaldıraç Kuralları Doğrulama Raporu

**Tarih:** 2 Haziran 2026  
**Durum:** ✅ **TÜM KURALLAR ANAYASAYA UYUMLU**

---

## 📋 Doğrulama Matriksi

### **1x Kaldıraç**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | Durum |
|-------|---------|------------------------|--------------|-------|
| Stop-Loss | 3% | 3% ✅ | 3.0% ✅ | ✅ |
| Savunma | Yok | defense_count: 0 ✅ | has_defense: False ✅ | ✅ |
| TP1 | 3% | tp1_pct: 3 ✅ | tp1_multiplier: 1.03 ✅ | ✅ |
| TP2 | 5% | tp2_pct: 5 ✅ | tp2_multiplier: 1.05 ✅ | ✅ |
| TP2 Kapat | 50% | tp2_close: 0.50 ✅ | tp1_ratio: 0.50 ✅ | ✅ |
| Trailing | 2% | trailing_callback: 2.0 ✅ | trailing_callback_pct: 2.0 ✅ | ✅ |
| TP Tipi | standard | tp_type: 'standard' ✅ | tp_type: 'standard' ✅ | ✅ |

### **2x Kaldıraç**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | Durum |
|-------|---------|------------------------|--------------|-------|
| Stop-Loss | 3% | 3% ✅ | 3.0% ✅ | ✅ |
| Savunma | Yok | defense_count: 0 ✅ | has_defense: False ✅ | ✅ |
| TP1 | 3% | tp1_pct: 3 ✅ | tp1_multiplier: 1.03 ✅ | ✅ |
| TP2 | 5% | tp2_pct: 5 ✅ | tp2_multiplier: 1.05 ✅ | ✅ |
| TP2 Kapat | 50% | tp2_close: 0.50 ✅ | tp1_ratio: 0.50 ✅ | ✅ |
| Trailing | 2% | trailing_callback: 2.0 ✅ | trailing_callback_pct: 2.0 ✅ | ✅ |
| TP Tipi | standard | tp_type: 'standard' ✅ | tp_type: 'standard' ✅ | ✅ |

### **3x Kaldıraç**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | config.py | Durum |
|-------|---------|------------------------|--------------|-----------|-------|
| Stop-Loss | 2% | 2% ✅ | 2.0% ✅ | **3% ❌ DÜZELTILDI→2%** | ✅ |
| Savunma | Yok | defense_count: 0 ✅ | has_defense: False ✅ | has_defense: False ✅ | ✅ |
| TP1 | 3% | tp1_pct: 3 ✅ | tp1_multiplier: 1.03 ✅ | — | ✅ |
| TP2 | 5% | tp2_pct: 5 ✅ | tp2_multiplier: 1.05 ✅ | — | ✅ |
| TP2 Kapat | 50% | tp2_close: 0.50 ✅ | tp1_ratio: 0.50 ✅ | — | ✅ |
| Trailing | 2% | trailing_callback: 2.0 ✅ | trailing_callback_pct: 2.0 ✅ | — | ✅ |
| TP Tipi | standard | tp_type: 'standard' ✅ | tp_type: 'standard' ✅ | — | ✅ |

### **4x Kaldıraç (⭐ DEFANS AKTİF)**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | Durum |
|-------|---------|------------------------|--------------|-------|
| Stop-Loss | Yok | None ✅ | None ✅ | ✅ |
| Savunma | D1, D2, D3 | defense_count: 3 ✅ | has_defense: True ✅ | ✅ |
| D1 Tetik | 95% giriş | — | trigger_multiplier: 0.95 ✅ | ✅ |
| D1 Ekleme | Slot/5 | — | slot_ratio: 0.20 ✅ | ✅ |
| D2 Tetik | 88% giriş | — | trigger_multiplier: 0.88 ✅ | ✅ |
| D2 Ekleme | Slot/5 | — | slot_ratio: 0.20 ✅ | ✅ |
| D3 Tetik | 75% giriş | — | trigger_multiplier: 0.75 ✅ | ✅ |
| D3 Ekleme | Slot×2/5 | — | slot_ratio: 0.40 ✅ | ✅ |
| TP1 | 3% | tp1_pct: 3 ✅ | tp1_multiplier: 1.03 ✅ | ✅ |
| TP2 | 5% | tp2_pct: 5 ✅ | tp2_multiplier: 1.05 ✅ | ✅ |
| Trailing | 2% | trailing_callback: 2.0 ✅ | trailing_callback_pct: 2.0 ✅ | ✅ |

### **5x Kaldıraç**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | Durum |
|-------|---------|------------------------|--------------|-------|
| Stop-Loss | 2% | 2% ✅ | 2.0% ✅ | ✅ |
| Savunma | Yok | defense_count: 0 ✅ | has_defense: False ✅ | ✅ |
| TP1 | 3% | tp1_pct: 3 ✅ | tp1_multiplier: 1.03 ✅ | ✅ |
| TP2 | 5% | tp2_pct: 5 ✅ | tp2_multiplier: 1.05 ✅ | ✅ |
| TP2 Kapat | 50% | tp2_close: 0.50 ✅ | tp1_ratio: 0.50 ✅ | ✅ |
| Trailing | 2% | trailing_callback: 2.0 ✅ | trailing_callback_pct: 2.0 ✅ | ✅ |
| TP Tipi | standard | tp_type: 'standard' ✅ | tp_type: 'standard' ✅ | ✅ |

### **6x Kaldıraç**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | Durum |
|-------|---------|------------------------|--------------|-------|
| Stop-Loss | 2% | 2% ✅ | 2.0% ✅ | ✅ |
| Savunma | Yok | defense_count: 0 ✅ | has_defense: False ✅ | ✅ |
| TP1 | 3% | tp1_pct: 3 ✅ | tp1_multiplier: 1.03 ✅ | ✅ |
| TP2 | 5% | tp2_pct: 5 ✅ | tp2_multiplier: 1.05 ✅ | ✅ |
| TP2 Kapat | 50% | tp2_close: 0.50 ✅ | tp1_ratio: 0.50 ✅ | ✅ |
| Trailing | 2% | trailing_callback: 2.0 ✅ | trailing_callback_pct: 2.0 ✅ | ✅ |
| TP Tipi | standard | tp_type: 'standard' ✅ | tp_type: 'standard' ✅ | ✅ |

### **7x Kaldıraç**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | Durum |
|-------|---------|------------------------|--------------|-------|
| Stop-Loss | 1.5% | 1.5% ✅ | 1.5% ✅ | ✅ |
| Savunma | Yok | defense_count: 0 ✅ | has_defense: False ✅ | ✅ |
| TP1 | 3% | tp1_pct: 3 ✅ | tp1_multiplier: 1.03 ✅ | ✅ |
| TP2 | 5% | tp2_pct: 5 ✅ | tp2_multiplier: 1.05 ✅ | ✅ |
| TP2 Kapat | 50% | tp2_close: 0.50 ✅ | tp1_ratio: 0.50 ✅ | ✅ |
| Trailing | 2% | trailing_callback: 2.0 ✅ | trailing_callback_pct: 2.0 ✅ | ✅ |
| TP Tipi | standard | tp_type: 'standard' ✅ | tp_type: 'standard' ✅ | ✅ |

### **8x Kaldıraç**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | Durum |
|-------|---------|------------------------|--------------|-------|
| Stop-Loss | 1% | 1% ✅ | 1.0% ✅ | ✅ |
| Savunma | Yok | defense_count: 0 ✅ | has_defense: False ✅ | ✅ |
| TP1 | 3% | tp1_pct: 3 ✅ | tp1_multiplier: 1.03 ✅ | ✅ |
| TP2 | 5% | tp2_pct: 5 ✅ | tp2_multiplier: 1.05 ✅ | ✅ |
| TP2 Kapat | 50% | tp2_close: 0.50 ✅ | tp1_ratio: 0.50 ✅ | ✅ |
| Trailing | 2% | trailing_callback: 2.0 ✅ | trailing_callback_pct: 2.0 ✅ | ✅ |
| TP Tipi | standard | tp_type: 'standard' ✅ | tp_type: 'standard' ✅ | ✅ |

### **9x Kaldıraç**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | Durum |
|-------|---------|------------------------|--------------|-------|
| Stop-Loss | 1% | 1% ✅ | 1.0% ✅ | ✅ |
| Savunma | Yok | defense_count: 0 ✅ | has_defense: False ✅ | ✅ |
| TP1 | 3% | tp1_pct: 3 ✅ | tp1_multiplier: 1.03 ✅ | ✅ |
| TP2 | 5% | tp2_pct: 5 ✅ | tp2_multiplier: 1.05 ✅ | ✅ |
| TP2 Kapat | 50% | tp2_close: 0.50 ✅ | tp1_ratio: 0.50 ✅ | ✅ |
| Trailing | 2% | trailing_callback: 2.0 ✅ | trailing_callback_pct: 2.0 ✅ | ✅ |
| TP Tipi | standard | tp_type: 'standard' ✅ | tp_type: 'standard' ✅ | ✅ |

### **10x Kaldıraç (FAST)**
| Kural | Anayasa | Motor (engine/main.py) | Mina Manager | Durum |
|-------|---------|------------------------|--------------|-------|
| Stop-Loss | 1% | 1% ✅ | 1.0% ✅ | ✅ |
| Savunma | Yok | defense_count: 0 ✅ | has_defense: False ✅ | ✅ |
| TP Tipi | fast | tp_type: 'fast' ✅ | tp_type: 'fast' ✅ | ✅ |
| TP1 | 2% | tp1_pct: 2 ✅ | tp1_multiplier: 1.02 ✅ | ✅ |
| TP1 Kapat | 50% | — | tp1_ratio: 0.50 ✅ | ✅ |
| TP2 | 4% | tp2_pct: 4 ✅ | tp2_multiplier: 1.04 ✅ | ✅ |
| TP2 Kapat | **100% (TÜM)** | tp2_close: 1.00 ✅ | tp2_ratio: 1.00 ✅ | ✅ |
| Trailing | **YOK** | trailing_callback: None ✅ | trailing_callback_pct: None ✅ | ✅ |

---

## 📊 Özet

### ✅ **Uyumlu Olan (10/10)**
- 1x: Tamamen uyumlu
- 2x: Tamamen uyumlu
- 3x: ✅ Düzeltildi (config.py: 3%→2%)
- 4x: Tamamen uyumlu (DEFANS AKTİF)
- 5x: Tamamen uyumlu
- 6x: Tamamen uyumlu
- 7x: Tamamen uyumlu
- 8x: Tamamen uyumlu
- 9x: Tamamen uyumlu
- 10x: Tamamen uyumlu (FAST MODE)

### ⚠️ **Düzeltmeleri Yapılan**
1. **backend/config.py** - 3x stop_loss: 3% → 2% (✅ DÜZELTILDI)

### 🔐 **Kritik Kurallar**
- **4x SADECE DEFANS:** SL=None, 3 seviye defans aktif ✅
- **Diğer Tüm Kaldıraçlar STOP-LOSS ile Korunuyor** ✅
- **10x TRAILING STOP YOK** (TP2 TÜMÜNÜ KAPAT) ✅

---

## ✍️ Doğrulama Ayrıntıları

### **1. engine/main.py — LEVERAGE_RULES**
**Dosya:** `engine/main.py` (satır 60-72)
```python
LEVERAGE_RULES = {
    1:  {'stop_loss': 3,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    2:  {'stop_loss': 3,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},
    3:  {'stop_loss': 2,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},  ✅
    4:  {'stop_loss': None, 'defense_count': 3, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},  ✅
    5:  {'stop_loss': 2,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},  ✅
    6:  {'stop_loss': 2,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},  ✅
    7:  {'stop_loss': 1.5,  'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},  ✅
    8:  {'stop_loss': 1,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},  ✅
    9:  {'stop_loss': 1,    'defense_count': 0, 'tp_type': 'standard', 'tp1_pct': 3, 'tp2_pct': 5, 'tp2_close': 0.50, 'trailing_callback': 2.0},  ✅
    10: {'stop_loss': 1,    'defense_count': 0, 'tp_type': 'fast',     'tp1_pct': 2, 'tp2_pct': 4, 'tp2_close': 1.00, 'trailing_callback': None},  ✅
}
```

### **2. mina_position_manager.py — leverage_rules**
**Dosya:** `mina_position_manager.py` (satır 36-45)
```python
self.leverage_rules = {
    1:  {'stop_loss_pct': 3.0,   'tp_type': 'standard', 'has_defense': False},  ✅
    2:  {'stop_loss_pct': 3.0,   'tp_type': 'standard', 'has_defense': False},  ✅
    3:  {'stop_loss_pct': 2.0,   'tp_type': 'standard', 'has_defense': False},  ✅
    4:  {'stop_loss_pct': None,  'tp_type': 'standard', 'has_defense': True},   ✅
    5:  {'stop_loss_pct': 2.0,   'tp_type': 'standard', 'has_defense': False},  ✅
    6:  {'stop_loss_pct': 2.0,   'tp_type': 'standard', 'has_defense': False},  ✅
    7:  {'stop_loss_pct': 1.5,   'tp_type': 'standard', 'has_defense': False},  ✅
    8:  {'stop_loss_pct': 1.0,   'tp_type': 'standard', 'has_defense': False},  ✅
    9:  {'stop_loss_pct': 1.0,   'tp_type': 'standard', 'has_defense': False},  ✅
    10: {'stop_loss_pct': 1.0,   'tp_type': 'fast',     'has_defense': False},   ✅
}
```

### **3. mina_position_manager.py — tp_rules**
**Dosya:** `mina_position_manager.py` (satır 47-63)
```python
self.tp_rules = {
    'standard': {
        'tp1_ratio': 0.50,
        'tp2_ratio': 0.50,
        'tp1_multiplier': 1.03,              # TP1 = Giriş × 1.03 = %3 ✅
        'tp2_multiplier': 1.05,              # TP2 = Giriş × 1.05 = %5 ✅
        'trailing_callback_pct': 2.0,        # Trailing = %2 ✅
    },
    'fast': {
        'tp1_ratio': 0.50,
        'tp2_ratio': 1.00,                   # 10x: TP2'de TÜM POZISYON KAPATILIR ✅
        'tp1_multiplier': 1.02,              # TP1 = Giriş × 1.02 = %2 ✅
        'tp2_multiplier': 1.04,              # TP2 = Giriş × 1.04 = %4 ✅
        'trailing_callback_pct': None,       # 10x: Trailing YOK ✅
    }
}
```

### **4. mina_position_manager.py — defense_rules**
**Dosya:** `mina_position_manager.py` (satır 65-68)
```python
self.defense_rules = {
    1: {'trigger_multiplier': 0.95, 'slot_ratio': 0.20},  # D1: Giriş×0.95, Slot/5 ✅
    2: {'trigger_multiplier': 0.88, 'slot_ratio': 0.20},  # D2: Giriş×0.88, Slot/5 ✅
    3: {'trigger_multiplier': 0.75, 'slot_ratio': 0.40},  # D3: Giriş×0.75, Slot×2/5 ✅
}
```

---

## 🎯 Sonuç

**STATUS: ✅ TAMAMLANMIŞ**

✅ Tüm 10 kaldıraç seviyesi MINA Anayasasına **milimetrik** uyumlu.  
✅ **4x SADECE DEFANS** ile korunuyor (SL=None, D1/D2/D3 aktif).  
✅ **Diğer Tüm Kaldıraçlar STOP-LOSS** ile korunuyor.  
✅ **10x FAST MODE** doğru: TP1=2%, TP2=4%, Trailing=None, TP2'de TÜMÜ KAPAT.  
✅ 1 küçük düzeltme yapıldı: **config.py 3x SL: 3%→2%**.

---

**Başmimarın Onayı Bekliyor ✋**
