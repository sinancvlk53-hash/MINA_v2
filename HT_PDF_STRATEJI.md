# HT PDF Strateji Kuralları
Son güncelleme: 10.06.2026

## 1. SİNYAL TESPİTİ
- TradingView Position Tool varsa → sinyal al
- Position Tool yoksa ama hoca notta "alın" diyorsa → al
- İkisi de yoksa → geç

## 2. YÖN TESPİTİ
- Yeşil YUKARI doğru büyükse → LONG
- Yeşil AŞAĞI doğru büyükse → SHORT
- Sadece yeşilin yönüne bak, kırmızıya bakma

## 3. FİYAT OKUMA
- Entry = yeşil ve kırmızının birleştiği çizgi
- TP = yeşilin dış ucu
- Stop = kırmızının dış ucu

## 4. İKİ YÖNLÜ POZİSYON
- Aynı grafikte iki Position Tool varsa → iki ayrı sinyal
- Üstteki ve alttaki ayrı değerlendir
- Her ikisi için limit emir aç
- Biri tetiklenince diğeri açık kalır

## 5. EMİR KURALLARI
- Her zaman LIMIT emir — asla MARKET
- Hoca'nın verdiği fiyattan girilir
- 4x kaldıraç — değişmez
- Stop yok — savunma sistemi (D1/D2/D3) çalışır

## 6. YENİ PDF GELİNCE
- Aynı coin için eski sinyal iptal
- Eski limit emir Binance'ten kaldırılır
- Yeni sinyal açılır

## 7. GEÇİLEN DURUMLAR
- Position Tool yok + not yok → geç
- Stop seviyesi yok → geç (4x hariç — 4x'te stop yok savunma var)
- FOREX coinler (XAU, XAG) → Binance'te varsa al, yoksa geç
- "Pas", "şu an değil" notu varsa ama Position Tool varsa → al

## 8. BAŞARI ORANI TAKİBİ
- Her sinyal ht_pdf_basari_orani tablosuna kaydedilir
- TP vurursa → tp_hit
- Stop vurursa → stop_hit
- Yeni PDF ile iptal olursa → cancelled
