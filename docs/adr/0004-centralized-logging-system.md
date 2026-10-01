# ADR 0004: Merkezi ve Destek Odaklı Loglama Sistemi

## Durum
Kabul Edildi

## Bağlam
Katib uygulaması, kullanıcıların sesini metne çeviren bir masaüstü uygulamasıdır. Uygulama `--noconsole` modunda (UI) çalıştığında, kütüphane hataları ve uygulama çökmeleri kullanıcı tarafından görülememekte, bu da teknik destek sürecini zorlaştırmaktadır. Mevcut loglama yapısı worker'lar ve UI arasında manuel sinyallerle kurulmuş olup DRY prensibine aykırı ve bakımı zordur.

## Kararlar

### 1. Hedef: Desteklenebilirlik (Supportability)
Loglama sisteminin birincil amacı, bir hata durumunda kullanıcının geliştiriciye gönderebileceği okunaklı "kara kutu" (black box) kayıtları oluşturmaktır.

### 2. Gizlilik ve Güvenlik (Privacy First)
- **Metin Filtreleme:** Varsayılan `INFO` seviyesinde loglarda transkripsiyon metinleri asla yer almaz. Sadece metadatalar (karakter sayısı, işlem süresi) kaydedilir.
- **Opsiyonel Debug:** Sadece kullanıcı ayarlardan `DEBUG` modunu açarsa, hata teşhisi için metin içerikleri loglanır.
- **Offline:** Loglar sadece yerel cihazda (`%LOCALAPPDATA%`) saklanır, hiçbir şekilde dışarı sızdırılmaz (telemetri yasaktır).

### 3. Mimari: Unified Log Handler (DRY)
- **Merkezi Dağıtıcı:** Worker'lar içindeki manuel `log_entry` sinyalleri yerine standart Python `logging` modülü kullanılır.
- **QtLogHandler:** Özel bir handler ile `logging` çağrıları otomatik olarak UI Dashboard'a (sinyal aracılığıyla) yönlendirilir.
- **İstisna:** Bu yapı `CONTEXT.md` içindeki "Global Event Bus" kuralına bir istisna olarak tanımlanmıştır.

### 4. Format: İnsan Dostu (Plain Text)
Loglar JSON yerine düz metin formatında tutulur. Format: `Zaman | Seviye | PID | Thread | Dosya:Satır | Mesaj`.

### 5. Dinamik Yapı
Log seviyesi (INFO/DEBUG) ve saklama kuralları `core/settings.py` üzerinden yönetilir.

### 6. Uygulama (Eylül 2026)
Bu ADR uzun süre uygulanmadan kaldı; worker'lar `log_entry` sinyalleriyle loglamaya devam etti ve transkript metinleri INFO seviyesinde `katib.log`'a yazıldı. Uygulanan hali:
- `core/log.py`: `get_logger(<BİLEŞEN>)` → `Katib.<BİLEŞEN>` logger'ı; başarılı adımlar için `OK` (25) seviyesi.
- Dikte edilen metin `extra={"transcript": metin}` ile verilir. `PrivacyFormatter` (dosya ve konsol) yalnızca uzunluğunu yazar: `Transcript (42 chars)`. `DashboardLogHandler` (QtLogHandler'ın karşılığı) metni ekranda gösterir.
- Yakalanmamış istisna dökümündeki yerel değişkenlerde string değerler `<str len=N>` olarak maskelenir.
- Dosya ve konsol yazması `QueueHandler`/`QueueListener` ile ayrı bir thread'de yapılır; log çağıran thread (ör. PortAudio callback'i) diske dokunmaz. Kapanışta `main.stop_logging()` kuyruğu boşaltır (plan 0004).
- Ayarlar penceresi ve dashboard'un olay satırları da `get_logger("APP")` / `get_logger("MIC")` üzerinden gider; `SettingsDialog.log_entry` sinyali kaldırıldı. Yalnız i18n anahtarlı ekran rehberleri (`no_mic_found`, `model_missing_guidance`) dashboard'a özeldir: olay değil, dil değişince yeniden çevrilen yönergedir (plan 0004).
- Henüz uygulanmayanlar: ayarlardan açılan DEBUG modu (bölüm 2) ve seviyenin `core/settings.py`'den yönetilmesi (bölüm 5).

## Sonuçlar
- **Artı:** Hata teşhisi hızlanır, kod miktarı (boilerplate) azalır.
- **Eksi:** Log akışı "implicit" (örtük) hale geldiği için `main.py`'daki başlatma satırı kritik öneme sahip olur.
