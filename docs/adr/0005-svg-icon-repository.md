# ADR-0005: SVG İkon Metinlerinin Tek Merkezde (ui/icons.py) Toplanması

## Durum
Kabul edildi.

## Bağlam
Harici dosya (`assets/`) bağımlılıklarını ortadan kaldırmak için ikonlar dinamik olarak boyanabilen çiğ (raw) SVG metinlerine dönüştürüldü. Ancak 300+ karakterlik XML/SVG dizgelerinin doğrudan UI kodlarının (`dashboard.py`, `tray_app.py`) içine yazılması, arayüz layout kodunun okunabilirliğini yok etmekteydi. `CONTEXT.md` Anti-Pattern #3 kuralı, 3'ten fazla tekrar etmeyen kodların ayrıştırılmasını "Erken Soyutlama" olarak yasaklamaktadır.

## Karar
Görsel varlıkların (Assets) ham metin karşılıkları, iş mantığı (Business Logic) veya bir kod soyutlaması sayılmaz. Bu sebeple "Erken Soyutlama" kuralına bir istisna olarak; tüm SVG dizgelerinin, projede sadece 1 kez bile kullanılsalar `ui/icons.py` adında saf bir değişken/sabit dosyasında toplanmasına karar verilmiştir.

## Gerekçe
- UI layout bloklarının dikey okunabilirliği korunur.
- Yarın başka bir bileşen mevcut ikona ihtiyaç duyarsa SSOT bozulmaz.
- Bu bir "Clean Architecture" hilesi değil, statik veriyi (Data) koddan (Logic) ayırma pratiğidir.

## Sonuçlar
Uygulamaya eklenecek yeni dinamik ikonlar doğrudan `ui/icons.py` dosyasına eklenmeli ve ilgili UI sınıflarından oradan import edilmelidir.