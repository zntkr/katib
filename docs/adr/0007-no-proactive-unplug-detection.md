# ADR-0007: Mikrofon Çıkarma Tespiti Kayıt Girişimine Ertelenmiştir

## Durum
Kabul edildi.

## Bağlam
Kullanıcı mikrofonu fiziksel olarak çıkardığında Dashboard'ın "Mikrofon Bağlı Değil" durumuna **anında** geçmesi istendi. Mevcut davranış: durum değişikliği, ancak kullanıcı kayıt tuşuna basıp `start_recording()` başarısız olduğunda tetiklenir.

Proaktif tespit için iki yaklaşım denendi:

1. **`QMediaDevices.audioInputs()` ile isim karşılaştırması**: Qt'nin `audioInputsChanged` sinyali, donanım değişimini gerçek zamanlı iletir. Ancak Qt (`QAudioDevice.description()`) ve PortAudio (`sd.query_devices()`) farklı isim formatları kullanır — Qt "USB Audio Device" derken PortAudio "Mikrofon (USB Audio Device)" der. Kısmi eşleştirme (`in` operatörü) da güvenilmez; bağlı ve meşru bir cihazın "Bağlı Değil" olarak işaretlenmesine yol açtı. Bu yaklaşım geri alındı.

2. **PortAudio cihaz listesi kontrolü**: `sd.query_devices()` Zombie Device'ı (bkz. CONTEXT.md) hâlâ listeler. Fiziksel kopuş tespiti için tek güvenilir yol `sd.InputStream` açmayı denemektir; bu da kullanıcı girişi olmadan arkaplanda tekrarlı stream açma girişimi anlamına gelir — kaynak israfı ve karmaşıklık getirir.

## Karar
Proaktif tespit eklenmeyecektir. `mic_unavailable` sinyali yalnızca `start_recording()` başarısızlıklarından ve `_on_stream_finished()` (beklenmedik kopuş) üzerinden tetiklenmeye devam edecektir.

Gerekçe:
- PortAudio'nun Zombie Device sınırlaması aşılmaz; güvenilir bir proaktif çözüm mevcut değildir.
- QMediaDevices ile isim eşleştirmesi denenmiş ve gerçek cihazları yanlış işaretlediği görülmüştür.
- Yanlış pozitif ("bağlı mic'i bağlı değil gösterme") kabul edilemez; yanlış negatif ("çıkarmayı gecikmeli fark etme") kabul edilebilir.

## Sonuçlar
- Kullanıcı mic'i çıkardıktan sonra kayıt tuşuna basmadan Dashboard "Hazır" göstermeye devam eder. Bu beklenen davranıştır, hata değildir.
- `_on_stream_finished()` hâlâ aktif kayıt sırasında fiziksel kopuşu anında yakalar — yalnızca pasif bekleme durumunda gecikme yaşanır.
- Bu limitasyonu "düzeltmeye" çalışan bir sonraki ajan bu ADR'ye bakmalıdır.
