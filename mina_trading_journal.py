# -*- coding: utf-8 -*-
"""
MİNA v2 - DERR (Veri Tabanlı Öz-Denetim ve İşlem Günlüğü)
Trading Journal — Professional Trading Metrics Database

Her işlem açıldığında ve kapandığında, tüm metrikleri SQLite'da kaydeder.
- Açılış/Kapanış tarihi ve saati
- Sembol, yön, kaldıraç
- Giriş/çıkış fiyatları
- Savunma durumu (D1/D2/D3)
- Çıkış nedeni (TP1/TP2/Trailing/Hard Stop/Başabaş)
- Net PnL (dolar bazında)
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Optional, List


class TradingJournal:
    """Profesyonel trading journal ve veri tabanı yöneticisi."""
    
    def __init__(self, db_path: str = 'mina_trading_journal.db'):
        """
        Trading journal veritabanını başlat.
        
        Args:
            db_path: SQLite veritabanı dosya yolu
        """
        self.db_path = db_path
        self.conn = None
        self._init_db()
    
    def _init_db(self) -> None:
        """Veritabanı ve tabloları oluştur."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.cursor()
            
            # ─ İŞLEM TABLOSU ─────────────────────────────────────────────
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    
                    -- Temel Bilgiler
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,              -- 'LONG' veya 'SHORT'
                    leverage INTEGER NOT NULL,       -- 1x, 2x, 3x, 4x, 5x, 10x
                    
                    -- Açılış Bilgileri
                    open_time TIMESTAMP NOT NULL,    -- İşlem açılış tarihi/saati
                    open_price REAL NOT NULL,        -- Giriş fiyatı
                    open_qty REAL NOT NULL,          -- Açılan miktar
                    open_notional REAL NOT NULL,     -- Notional value (fiyat × miktar)
                    initial_margin REAL NOT NULL,    -- Başlangıç marjini
                    
                    -- Savunma Durumu
                    defense_triggered INTEGER DEFAULT 0,  -- 0=Yok, 1=D1, 2=D2, 3=D3
                    defense_prices TEXT,             -- JSON: {"D1": 95000, "D2": 88000, ...}
                    weighted_avg_price REAL,         -- Ağırlıklı ortalama (defans sonrası)
                    
                    -- Kapanış Bilgileri
                    close_time TIMESTAMP,            -- İşlem kapanış tarihi/saati
                    close_price REAL,                -- Çıkış fiyatı
                    close_qty REAL,                  -- Kapatılan miktar
                    close_reason TEXT,               -- 'TP1', 'TP2', 'Trailing', 'Hard Stop', 'Başabaş', 'Acil Tasfiye'
                    
                    -- PnL Metrikleri
                    pnl_percent REAL,                -- Yüzde bazında PnL
                    pnl_usdt REAL,                   -- Dolar bazında net zarar/kâr
                    roe_percent REAL,                -- Return on Equity (%)
                    
                    -- Durumu
                    status TEXT NOT NULL DEFAULT 'open',  -- 'open' veya 'closed'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ─ INDEX'LER ─────────────────────────────────────────────────
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_symbol ON trades(symbol)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_status ON trades(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_open_time ON trades(open_time)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_close_time ON trades(close_time)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_side ON trades(side)
            ''')

            try:
                cursor.execute("ALTER TABLE trades ADD COLUMN signal_source TEXT")
            except sqlite3.OperationalError:
                pass

            # ─ SİNYAL KARAR GÜNLÜĞÜ (Katman 1-3 audit) ───────────────────
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signal_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_label TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    merter_symbol TEXT,
                    merter_direction TEXT,
                    trading_session TEXT,
                    has_sfp INTEGER DEFAULT 0,
                    total_direction TEXT,
                    k1_json TEXT,
                    k2_verdict TEXT,
                    k2_brightness INTEGER,
                    k2_label TEXT,
                    k2_reason TEXT,
                    k3_action TEXT,
                    k3_reason TEXT,
                    final_label TEXT
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_signal_scenario
                ON signal_decisions(scenario_label)
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS haluk_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    message_id INTEGER,
                    raw_text TEXT NOT NULL,
                    message_type TEXT NOT NULL DEFAULT 'diger',
                    coins_mentioned TEXT,
                    direction TEXT,
                    price_levels TEXT,
                    analysis_summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_haluk_ts ON haluk_messages(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_haluk_type ON haluk_messages(message_type)
            ''')
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_haluk_message_id
                ON haluk_messages(message_id) WHERE message_id IS NOT NULL
            ''')
            
            self.conn.commit()
            
        except Exception as e:
            print(f"❌ Journal DB init hatası: {e}")
            raise

    def log_signal_decision(
        self,
        *,
        scenario_label: str,
        merter_symbol: str,
        merter_direction: str,
        trading_session: str,
        has_sfp: bool,
        total_direction: Optional[str],
        k1: Dict,
        k2: Dict,
        k3: Dict,
    ) -> int:
        """Katman 1-3 sinyal değerlendirmesini DERR'e yaz."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                '''
                INSERT INTO signal_decisions (
                    scenario_label, merter_symbol, merter_direction, trading_session,
                    has_sfp, total_direction, k1_json, k2_verdict, k2_brightness,
                    k2_label, k2_reason, k3_action, k3_reason, final_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    scenario_label,
                    merter_symbol,
                    merter_direction,
                    trading_session,
                    1 if has_sfp else 0,
                    total_direction,
                    json.dumps(k1, ensure_ascii=False),
                    k2.get("verdict"),
                    k2.get("brightness"),
                    k2.get("label"),
                    k2.get("reason"),
                    k3.get("action"),
                    k3.get("reason"),
                    k2.get("label"),
                ),
            )
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"❌ Journal signal_decision hatası: {e}")
            return -1

    def log_trade_open(self, symbol: str, side: str, leverage: int, 
                       entry_price: float, qty: float, initial_margin: float,
                       signal_source: Optional[str] = None) -> int:
        """
        İşlem açıldığında kaydı başlat.
        
        Args:
            symbol: Sembol (BTCUSDT)
            side: LONG veya SHORT
            leverage: Kaldıraç
            entry_price: Giriş fiyatı
            qty: Açılan miktar
            initial_margin: Başlangıç marjini
        
        Returns:
            Trade ID
        """
        try:
            cursor = self.conn.cursor()
            notional = entry_price * qty
            
            if signal_source:
                cursor.execute('''
                INSERT INTO trades 
                (symbol, side, leverage, open_time, open_price, open_qty, 
                 open_notional, initial_margin, status, signal_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, side, leverage, 
                datetime.now(),
                entry_price, qty,
                notional, initial_margin,
                'open', signal_source,
            ))
            else:
                cursor.execute('''
                INSERT INTO trades 
                (symbol, side, leverage, open_time, open_price, open_qty, 
                 open_notional, initial_margin, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, side, leverage, 
                datetime.now(),
                entry_price, qty,
                notional, initial_margin,
                'open'
            ))
            
            self.conn.commit()
            trade_id = cursor.lastrowid
            
            print(f"📔 [Journal] İşlem başlangıç kaydı: ID={trade_id} {symbol} {side} {leverage}x")
            return trade_id
            
        except Exception as e:
            print(f"❌ Journal trade_open hatası: {e}")
            return -1

    def log_defense_triggered(self, trade_id: int, defense_level: int, 
                             defense_prices: Dict, weighted_avg: float) -> None:
        """
        Savunma tetiklendiğinde kaydı güncelle.
        
        Args:
            trade_id: İşlem ID'si
            defense_level: 1, 2 veya 3
            defense_prices: Savunma fiyatları
            weighted_avg: Ağırlıklı ortalama fiyat
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('''
                UPDATE trades
                SET defense_triggered = ?,
                    defense_prices = ?,
                    weighted_avg_price = ?
                WHERE id = ?
            ''', (
                defense_level,
                json.dumps(defense_prices),
                weighted_avg,
                trade_id
            ))
            
            self.conn.commit()
            
            print(f"📔 [Journal] D{defense_level} tetiklendi: Trade ID={trade_id}")
            
        except Exception as e:
            print(f"❌ Journal defense_triggered hatası: {e}")

    def log_trade_close(self, trade_id: int, close_price: float, qty: float,
                       close_reason: str, pnl_usdt: float, pnl_percent: float,
                       roe_percent: float) -> None:
        """
        İşlem kapandığında kaydı tamamla.
        
        Args:
            trade_id: İşlem ID'si
            close_price: Çıkış fiyatı
            qty: Kapatılan miktar
            close_reason: Kapanış nedeni
            pnl_usdt: Net PnL (dolar)
            pnl_percent: Yüzde PnL
            roe_percent: ROE yüzdesi
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('''
                UPDATE trades
                SET close_time = ?,
                    close_price = ?,
                    close_qty = ?,
                    close_reason = ?,
                    pnl_usdt = ?,
                    pnl_percent = ?,
                    roe_percent = ?,
                    status = ?
                WHERE id = ?
            ''', (
                datetime.now(),
                close_price, qty,
                close_reason,
                pnl_usdt, pnl_percent,
                roe_percent,
                'closed',
                trade_id
            ))
            
            self.conn.commit()
            
            emoji = "📈" if pnl_usdt >= 0 else "📉"
            print(f"📔 [Journal] İşlem kapalı: ID={trade_id} {close_reason} {emoji} PnL: ${pnl_usdt:+.2f}")
            
        except Exception as e:
            print(f"❌ Journal trade_close hatası: {e}")

    def reconcile_open_qty(
        self,
        trade_id: int,
        qty: float,
        initial_margin: float,
    ) -> bool:
        """Kısmi TP sonrası açık qty / notional / marjin güncelle."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE trades
                SET open_qty = ?,
                    open_notional = open_price * ?,
                    initial_margin = ?
                WHERE id = ? AND status = 'open'
                """,
                (qty, qty, initial_margin, trade_id),
            )
            self.conn.commit()
            if cursor.rowcount == 0:
                print(f"❌ Journal reconcile_open_qty: trade id={trade_id} bulunamadi veya kapali")
                return False
            print(
                f"📔 [Journal] Reconcile: id={trade_id} qty={qty} margin={initial_margin:.4f}"
            )
            return True
        except Exception as e:
            print(f"❌ Journal reconcile_open_qty hatası: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    # İSTATİSTİK VE RAPORLAMA
    # ─────────────────────────────────────────────────────────────────────

    def get_statistics(self, limit: int = 100) -> Dict:
        """
        Son N işlemin istatistiklerini hesapla.
        
        Args:
            limit: Kaç işlem incelenecek (sample size)
        
        Returns:
            İstatistik sözlüğü
        """
        try:
            cursor = self.conn.cursor()
            
            # Son N kapalı işlemi getir
            cursor.execute('''
                SELECT pnl_usdt, pnl_percent, side, leverage, close_reason, 
                       defense_triggered, symbol
                FROM trades
                WHERE status = 'closed'
                ORDER BY close_time DESC
                LIMIT ?
            ''', (limit,))
            
            trades = cursor.fetchall()
            
            if not trades:
                return {
                    'sample_size': 0,
                    'total_trades': 0,
                    'message': 'Kapalı işlem bulunamadı'
                }
            
            # Hesaplamalar
            total_pnl = sum(t['pnl_usdt'] for t in trades)
            winning_trades = [t for t in trades if t['pnl_usdt'] > 0]
            losing_trades = [t for t in trades if t['pnl_usdt'] < 0]
            break_even = [t for t in trades if t['pnl_usdt'] == 0]
            
            win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0
            avg_win = (sum(t['pnl_usdt'] for t in winning_trades) / len(winning_trades)) if winning_trades else 0
            avg_loss = (sum(t['pnl_usdt'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
            
            # Savunma analizi
            defended = [t for t in trades if t['defense_triggered'] > 0]
            defense_win_rate = (sum(1 for t in defended if t['pnl_usdt'] > 0) / len(defended) * 100) if defended else 0
            
            # Kaldıraç analizi
            leverage_stats = {}
            for lev in [1, 2, 3, 4, 5, 10]:
                lev_trades = [t for t in trades if t['leverage'] == lev]
                if lev_trades:
                    lev_pnl = sum(t['pnl_usdt'] for t in lev_trades)
                    leverage_stats[lev] = {
                        'count': len(lev_trades),
                        'total_pnl': lev_pnl,
                        'avg_pnl': lev_pnl / len(lev_trades),
                        'win_count': sum(1 for t in lev_trades if t['pnl_usdt'] > 0)
                    }
            
            return {
                'sample_size': len(trades),
                'total_pnl_usdt': round(total_pnl, 2),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'break_even': len(break_even),
                'win_rate_percent': round(win_rate, 2),
                'avg_win_usdt': round(avg_win, 2),
                'avg_loss_usdt': round(avg_loss, 2),
                'profit_factor': round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0,
                'defended_trades': len(defended),
                'defense_win_rate': round(defense_win_rate, 2),
                'leverage_breakdown': leverage_stats,
                'top_symbols': self._get_top_symbols(trades, limit=5)
            }
            
        except Exception as e:
            print(f"❌ Statistics hatası: {e}")
            return {}

    def _get_top_symbols(self, trades: list, limit: int = 5) -> Dict:
        """Semboller için performans analizi."""
        symbol_stats = {}
        for trade in trades:
            sym = trade['symbol']
            if sym not in symbol_stats:
                symbol_stats[sym] = {'count': 0, 'pnl': 0}
            symbol_stats[sym]['count'] += 1
            symbol_stats[sym]['pnl'] += trade['pnl_usdt']
        
        sorted_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)
        return {sym: stats for sym, stats in sorted_symbols[:limit]}

    def print_statistics(self, limit: int = 100) -> None:
        """İstatistikleri güzel formatta ekrana bas."""
        stats = self.get_statistics(limit)
        
        if not stats or stats.get('sample_size') == 0:
            print("⚠️  İstatistik için yeterli veri yok")
            return
        
        print(f"\n{'='*70}")
        print(f"📊 TRADİNG JOURNAL İSTATİSTİKLERİ (Son {stats['sample_size']} İşlem)")
        print(f"{'='*70}")
        
        print(f"\n💰 ÖZET:")
        print(f"   Total PnL: ${stats['total_pnl_usdt']:+.2f}")
        print(f"   Başarılı: {stats['winning_trades']} | Başarısız: {stats['losing_trades']} | Başabaş: {stats['break_even']}")
        print(f"   Başarı Oranı: {stats['win_rate_percent']:.1f}%")
        print(f"   Ortalama Kâr: ${stats['avg_win_usdt']:.2f}")
        print(f"   Ortalama Zarar: ${stats['avg_loss_usdt']:.2f}")
        print(f"   Kar Faktörü: {stats['profit_factor']:.2f}")
        
        print(f"\n🛡️  SAVUNMA ANALİZİ:")
        print(f"   Tetiklenen: {stats['defended_trades']} ({stats['defended_trades']/stats['sample_size']*100:.1f}%)")
        print(f"   D1/D2/D3 Başarı Oranı: {stats['defense_win_rate']:.1f}%")
        
        print(f"\n⚙️  KALDIRAC İSTATİSTİKLERİ:")
        for lev in sorted(stats['leverage_breakdown'].keys()):
            lev_data = stats['leverage_breakdown'][lev]
            print(f"   {lev}x: {lev_data['count']} işlem | "
                  f"PnL: ${lev_data['total_pnl']:+.2f} | "
                  f"Avg: ${lev_data['avg_pnl']:+.2f} | "
                  f"Wins: {lev_data['win_count']}")
        
        print(f"\n🏆 EN İYİ SEMBOLLER:")
        for sym, sym_stats in stats['top_symbols'].items():
            print(f"   {sym}: {sym_stats['count']} işlem | PnL: ${sym_stats['pnl']:+.2f}")
        
        print(f"{'='*70}\n")

    def export_trades_csv(self, output_file: str = 'trades.csv', limit: int = 1000) -> None:
        """İşlemleri CSV dosyasına dışa aktar."""
        try:
            import csv
            cursor = self.conn.cursor()
            
            cursor.execute('''
                SELECT * FROM trades WHERE status = 'closed'
                ORDER BY close_time DESC LIMIT ?
            ''', (limit,))
            
            trades = cursor.fetchall()
            
            if not trades:
                print("⚠️  Dışa aktarılacak işlem yok")
                return
            
            headers = [description[0] for description in cursor.description]
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for trade in trades:
                    writer.writerow(trade)
            
            print(f"✅ {len(trades)} işlem '{output_file}'ye dışa aktarıldı")
            
        except Exception as e:
            print(f"❌ CSV dışa aktarma hatası: {e}")

    def get_trade_history(self, symbol: Optional[str] = None, 
                         limit: int = 50) -> List[Dict]:
        """
        İşlem geçmişini getir.
        
        Args:
            symbol: Filtre için sembol (None = tümü)
            limit: Kaç işlem
        
        Returns:
            İşlem listesi
        """
        try:
            cursor = self.conn.cursor()
            
            if symbol:
                cursor.execute('''
                    SELECT * FROM trades 
                    WHERE symbol = ? AND status = 'closed'
                    ORDER BY close_time DESC LIMIT ?
                ''', (symbol, limit))
            else:
                cursor.execute('''
                    SELECT * FROM trades 
                    WHERE status = 'closed'
                    ORDER BY close_time DESC LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"❌ get_trade_history hatası: {e}")
            return []

    def get_today_realized_pnl(self) -> float:
        """Bugün kapanan işlemlerin toplam realize PnL (USDT)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(SUM(pnl_usdt), 0)
                FROM trades
                WHERE status = 'closed'
                  AND date(close_time) = date('now', 'localtime')
                """
            )
            row = cursor.fetchone()
            return float(row[0] if row else 0.0)
        except Exception as e:
            print(f"❌ get_today_realized_pnl hatası: {e}")
            return 0.0

    def haluk_message_exists(self, message_id: Optional[int]) -> bool:
        if message_id is None:
            return False
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT 1 FROM haluk_messages WHERE message_id = ? LIMIT 1",
                (message_id,),
            )
            return cur.fetchone() is not None
        except Exception:
            return False

    def insert_haluk_message(
        self,
        *,
        timestamp: str,
        message_id: Optional[int],
        raw_text: str,
        message_type: str = "diger",
        coins_mentioned: Optional[List[str]] = None,
        direction: Optional[str] = None,
        price_levels: Optional[List] = None,
        analysis_summary: Optional[str] = None,
    ) -> int:
        try:
            cur = self.conn.cursor()
            cur.execute(
                '''
                INSERT OR IGNORE INTO haluk_messages (
                    timestamp, message_id, raw_text, message_type,
                    coins_mentioned, direction, price_levels, analysis_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    timestamp,
                    message_id,
                    raw_text,
                    message_type,
                    json.dumps(coins_mentioned or [], ensure_ascii=False),
                    direction,
                    json.dumps(price_levels or [], ensure_ascii=False),
                    analysis_summary,
                ),
            )
            self.conn.commit()
            return cur.lastrowid or 0
        except Exception as e:
            print(f"❌ insert_haluk_message hatası: {e}")
            return -1

    def list_haluk_messages(
        self,
        *,
        coin: Optional[str] = None,
        message_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict:
        try:
            clauses = ["1=1"]
            params: list = []
            if message_type and message_type != "all":
                clauses.append("message_type = ?")
                params.append(message_type)
            if date_from:
                clauses.append("timestamp >= ?")
                params.append(date_from)
            if date_to:
                clauses.append("timestamp <= ?")
                params.append(date_to + " 23:59:59")
            if coin:
                clauses.append(
                    "(coins_mentioned LIKE ? OR raw_text LIKE ?)"
                )
                c = coin.upper().replace("USDT", "")
                params.extend([f'%"{c}"%', f"%{c}%"])

            where = " AND ".join(clauses)
            cur = self.conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM haluk_messages WHERE {where}", params)
            total = int(cur.fetchone()[0])

            cur.execute(
                f'''
                SELECT id, timestamp, message_id, raw_text, message_type,
                       coins_mentioned, direction, price_levels, analysis_summary, created_at
                FROM haluk_messages
                WHERE {where}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                ''',
                params + [limit, offset],
            )
            rows = []
            for row in cur.fetchall():
                item = dict(row)
                try:
                    item["coins_mentioned"] = json.loads(item.get("coins_mentioned") or "[]")
                except json.JSONDecodeError:
                    item["coins_mentioned"] = []
                try:
                    item["price_levels"] = json.loads(item.get("price_levels") or "[]")
                except json.JSONDecodeError:
                    item["price_levels"] = []
                rows.append(item)
            return {"total": total, "items": rows}
        except Exception as e:
            print(f"❌ list_haluk_messages hatası: {e}")
            return {"total": 0, "items": []}

    def close(self) -> None:
        """Veritabanı bağlantısını kapat."""
        if self.conn:
            self.conn.close()
            print("✅ Journal DB kapatıldı")

    def __del__(self):
        """Destructor'da DB'yi kapat."""
        self.close()


if __name__ == '__main__':
    # TEST
    journal = TradingJournal()
    
    # Örnek işlem aç
    trade_id = journal.log_trade_open(
        symbol='BTCUSDT',
        side='LONG',
        leverage=4,
        entry_price=77000.0,
        qty=0.00129,
        initial_margin=25.0
    )
    
    # Savunma tetikle
    journal.log_defense_triggered(
        trade_id=trade_id,
        defense_level=1,
        defense_prices={'D1': 73150, 'D2': 67760, 'D3': 57750},
        weighted_avg=76500.0
    )
    
    # İşlem kapat
    journal.log_trade_close(
        trade_id=trade_id,
        close_price=78000.0,
        qty=0.00129,
        close_reason='TP2',
        pnl_usdt=25.50,
        pnl_percent=1.29,
        roe_percent=102.0
    )
    
    # İstatistikleri göster
    journal.print_statistics()
