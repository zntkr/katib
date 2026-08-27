# ADR-0008: SettingsDialog'da Erken Soyutlamadan (Premature Abstraction) Kaçınma

## Durum
Kabul edildi.

## Bağlam
`ui/settings_dialog.py` içindeki model yönetimi mantığı (combo box senkronizasyonu, badge render'ı, yol çözümleme, indirme orkestrasyonu), ~200 satıra ulaşmış ve tek bir diyalog sınıfının içinde 9 ayrı metoda dağılmıştır. Mimari inceleme sırasında, bu mantığın `ModelSelectionModule` adlı ayrı bir bileşene (3 metodlu bir arayüzle) çıkarılması "güçlü" bir aday olarak önerilmiştir.

Bu öneri insan yazılımcı standartlarında "Clean Architecture" ve sorumlulukların ayrılması açısından mantıklı görünse de, Katib projesi AI ajanları tarafından geliştirilmektedir ve CONTEXT.md kurallarına tabidir.

## Karar
`SettingsDialog` içindeki model yönetim mantığı tek dosyada, mevcut halinde bırakılacaktır. Ayrı bir modüle bölünmeyecektir.

Gerekçe:
- **Anti-Pattern #3 İhlali (Erken Soyutlama):** Kod yalnızca tek bir yerde (SettingsDialog) kullanılmaktadır. "Aynı kod 3'ten fazla kez tekrar ederse veya test edilebilirliği kesin olarak engelliyorsa" refactor edilir. Bu kod test edilebilirliği engellememektedir ve tekrar etmemektedir.
- **Keşif Friksiyonu Ajanlar İçin Önemsizdir:** Mantığın tek dosyada olması (200 satır), AI ajanının kodu saniyeler içinde grep ve context-window kullanarak kavramasını kolaylaştırır. Oysa iki dosyaya ayırmak, ekstra soyutlama katmanı ve arayüz zorunluluğu yaratır.
- **Yalınlık:** Ajan için "tek dosya", "ara yüzler arkasına gizlenmiş iki dosyadan" daha basit ve düzenlemesi daha az hata üreten bir yapıdır.

## Sonuçlar
- Ajanlar `settings_dialog.py` üzerinde çalışırken dosyanın boyutundan şikayet etmemeli veya onu parçalamaya çalışmamalıdır.
- Arayüz küçültme (interface shrinking) veya salt kozmetik (daha temiz görünüm) amaçlı dosya bölmeleri Katib projesinde aşırı mühendislik kabul edilerek reddedilmeye devam edecektir.
