# Katib — Bağlam Dokümanı (CONTEXT.md)

Bu doküman, Katib projesinin alan dilini, mimari yapısını ve temel çalışma prensiplerini tanımlar. **Bu dosya, AI ajanın tek kurumsal hafızasıdır.** Her oturum sıfırdan başlar; önceki konuşmaların hafızası yoktur. Bu dosyayı okumadan mimari karar verme, refactor önerme veya derin teşhis yapma.

---

## Geliştirme Modeli: AI-Ajan Projesi

Bu proje **tamamen AI ajanları tarafından geliştirilmektedir.** Hiçbir satır kod insan tarafından elle yazılmaz.

### Roller

| Rol | Sorumlu |
|-----|---------|
| **Ne yapılacak** (özellik, öncelik) | İnsan (proje sahibi) |
| **Nasıl yapılacak** (implementasyon, mimari) | İnsan ile istişare edilerek AI ajan |
| **Kod review, test onayı, PR merge** | AI ajan |

### Oturum Sürekliliği Yok

Her AI oturumu önceki konuşmaları bilmez. Bu şu anlama gelir:

- Bir önceki oturumda reddedilen bir yaklaşım, bağlam olmadan yeniden önerilebilir.
- "Daha önce konuşmuştuk" diye bir şey yoktur — kararlar bu dosyada ve `docs/adr/` içinde belgelenmelidir.
- Bu dosyanın eksik veya yanlış olması, iyi niyetli bir ajanın kötü karar almasına doğrudan yol açar.

### AI-Ajan Bağlamında Mimari Değerlendirme

İnsan geliştirici projelerinde geçerli olan bazı trade-off'lar bu projede farklı ağırlık taşır:

**Geçerli olmayan endişeler:**
- **Keşif friksiyonu** ("3 dosya açmak gerekiyor"): AI ajan grep ve paralel okuma ile bunu saniyeler içinde yapar. Kod lokalitesi insan belleği için değerlidir (7±2 sınırı), ajan için değil.
- **Tekrarlayan boilerplate**: Ajan için yazmak zor değildir; soyutlama maliyeti faydayı geçebilir.

**Hâlâ geçerli olan endişeler:**
- **Sessiz kopuşlar** (silent failures): Bir sinyal adı değişir ve bağlantı sessizce koparsa ajan da fark etmez — test suite yoksa hiç fark edilmez.
- **Test suite birincil güvenlik ağıdır**: İnsan review yoktur. Testlerin yetersiz olduğu bir alanda yapılan değişiklik, fark edilmeden production'a gider.
- **CONTEXT.md ve ADR'ler yük taşıyan belgelerdir**: Bir karar burada belgelenmemişse, bir sonraki ajan onu bilmez ve yeniden tartışır ya da tersine çevirir.

### Bu Dosyayı Okuyan Ajan İçin Pratik Kurallar

1. Bir refactor veya yeniden yapılanma önereceksen, önce bu dosyada ve `docs/adr/` içinde o konuyu ele alan bir kayıt olup olmadığını kontrol et.
2. "İnsan geliştirici için zor" ile "AI ajan için zor"u ayırt et. Bağlam belgelenmemişse ilki geçersizdir.
3. Bir karar reddedildiyse ve neden reddedildiği load-bearing bir gerekçeye dayanıyorsa, ADR yaz — yoksa bir sonraki ajan aynı öneriyle gelir.
4. Test suite'in kapsamadığı bir alanda değişiklik yapıyorsan, önce test yaz.

---

## Proje Amacı
Katib, Windows üzerinde çalışan, tamamen çevrimdışı (offline) bir ses-metin dönüştürme (STT) uygulamasıdır. Kullanıcının klavye kullanmadan, sadece konuşarak metin girişi yapmasını sağlar.

## Temel İş Akışı
1. **Dinleme**: `HotkeyWorker` global kısayolu (varsayılan: F9) izler.
2. **Kayıt**: Tuşa basıldığında `AudioWorker` mikrofonu açar ve ses verisini toplar.
3. **İşleme**: Tuş bırakıldığında toplanan ses verisi `TranscriptionWorker`'a iletilir.
4. **Dönüştürme**: `faster-whisper` kütüphanesi kullanılarak ses metne çevrilir.
5. **Yazma**: Üretilen metin `inject_text` fonksiyonu aracılığıyla imlecin bulunduğu yere sanal klavye vuruşları olarak gönderilir.

## Teknik Sözlük (Domain Language)

### Worker'lar (İş Parçacıkları)
- **HotkeyWorker**: İşletim sistemi seviyesinde tuş vuruşlarını dinleyen QThread.
- **AudioWorker**: Ses kartından ham PCM verisini yakalayan ve RMS (ses seviyesi) hesaplayan QThread.
- **TranscriptionWorker**: Whisper modelini bellekte tutan ve asıl ağır işi (çeviriyi) yapan kuyruk tabanlı QThread.
- **ModelDownloaderWorker**: Whisper modellerini HuggingFace üzerinden indiren yardımcı worker.

### Kavramlar
- **VAD (Voice Activity Detection)**: Ses içindeki sessiz bölümleri ayıklayan filtre.
- **Hallucination Filter**: Whisper'ın sessizlik anında uydurduğu "Teşekkürler", "Sessiz" gibi kelimeleri temizleyen mantıksal katman.
- **Deferred Initialization**: Uygulama açılışında "beyaz ekran" oluşmasını önlemek için worker'ların ve ağır modellerin yüklenmesini geciktiren mekanizma.
- **Theme Manager**: Uygulamanın koyu/açık tema ve renk paletini yöneten merkezi birim.
- **OSD (Status Indicator)**: Katib esnasında ekranın alt-ortasında beliren, etkileşimsiz (click-through) ve minimalist durum göstergesi. Kayıt/işleme durumu ve kritik hataların tek operasyonel görünürlük kanalıdır.
- **Armored Logic (Zırhlı Mantık)**: İşçi (Worker) seviyesinde başlayan, sistem hatalarını (örn. Mute durumu) proaktif olarak tespit edip kullanıcıyı uyaran korumacı mühendislik katmanı.
- **Binary Armor (İkili Zırh)**: "Ölü veya Canlı" prensibi. Sinyal matematiksel olarak tam sıfır (0.0) ise hata (Mute) kabul edilir; 0.0'dan büyük her sinyal (fısıltı dahil) geçerli kabul edilerek işlenir.
- **Zombie Device (Hayalet Cihaz)**: Fiziksel bağlantısı kesilmiş olmasına rağmen PortAudio'nun (ve Windows sürücüsünün) hâlâ listelemaya devam ettiği mikrofon. `sd.query_devices()` cihazı gösterir, ancak `sd.InputStream` açılmaya çalışıldığında PortAudio hatası (-9996 / Invalid device) fırlatır. `QMediaDevices.audioInputs()` (Qt) ve `sd.query_devices()` (PortAudio) farklı isim formatları kullandığından iki liste arasında güvenilir isim eşleştirmesi yapılamaz. Bkz. ADR-0007.

## Mimari Kurallar
1. **Thread Güvenliği**: UI bileşenlerine doğrudan diğer thread'lerden erişilemez. Tüm iletişim Qt Sinyalleri (Signals) üzerinden yapılmalıdır.
2. **Heavy Operations**: Model yükleme, ses işleme ve disk işlemleri asla ana thread'de (UI thread) yapılmaz.
3. **Single Instance**: Uygulama aynı anda sadece bir kez çalışabilir (Windows Mutex ile kontrol edilir).
4. **Graceful Shutdown**: Uygulama kapanırken worker'lar belirli bir sırayla (Hotkey -> Audio -> Transcription) durdurulur ve OS seviyesinde `os._exit(0)` ile temiz kapanış yapılır.
5. **Event Debouncing (Olay Susturma)**: İşletim sistemi kaynaklı donanım sinyalleri (ör. `QMediaDevices` mikrofon tak-çıkar uyarıları) bazen saniyede onlarca kez tetiklenerek bir "Event Storm" (sinyal fırtınası) yaratabilir. Bu tarz donanımsal veya yoğun GUI sinyallerini yakalarken doğrudan Worker'ları veya ağır işlemleri tetiklemek yerine, mutlaka `QTimer` kullanılarak **Debounce** (geciktirme/filtreleme) mantığı kurulmalıdır. Sinyaller yatışana kadar (ör. 500ms) beklenmeli ve işlem sadece 1 kez yapılmalıdır.
6. **Live UI ve State Yönetimi**: Ayarlar ekranındaki etkileşimler anında (Live) uygulanmalıdır. Uzun metin girişleri (örn. QLineEdit) için I/O spamını önlemek adına "Kaydet" butonu eklenebilir, ancak pencere kapanırken "Kaydetmeden Çıkıyorsunuz" gibi kullanıcıyı bloke eden (blocking modal) uyarılar **kesinlikle yasaktır**. Değişiklik yokken "Kaydet" butonunun pasif (disabled) yapılması, durum yönetimi (State) için yeterli ve doğru geri bildirimdir.
7. **Güvenli Kapanış ve Bellek Yönetimi (UI Teardown)**: Tüm üst düzey arayüz bileşenleri (Pencereler, OSD, Dialoglar), `closeEvent` metodunu ezerek içerdikleri aktif `QTimer` ve `QPropertyAnimation` nesnelerini (`findChildren` aracılığıyla) manuel olarak durdurmalıdır. Özellikle "Event Debouncing" kaynaklı zamanlayıcıların C++ belleğinde asılı kalıp test süreçlerini (Pytest) bozmasını önlemek için bu "explicit cleanup" zorunludur.

## Dosya Yapısı ve Sorumluluklar
- `main.py`: Uygulamanın giriş noktası ve sinyal yönlendirme merkezi.
- `ui/`: Tüm görsel arayüz bileşenleri (Dashboard, Tray, Dialogs).
- `workers/`: İş mantığını yürüten arka plan thread'leri.
- `core/`: Ayarlar, metin enjeksiyonu ve tema gibi çekirdek yardımcı işlevler.
- `ui/osd.py`: Operasyonel geri bildirim için kullanılan minimalist gösterge katmanı.
- `tests/`: Uygulamanın stabilitesini ölçen birim ve entegrasyon testleri.

## Geliştirici Notları
- Yeni bir ayar eklenirken `core/settings.py` üzerinden geçilmeli ve varsayılan değeri tanımlanmalıdır.
- Kullanıcıya gösterilecek tüm hatalar hem `TrayApp.show_error` (tray balonu) hem de OSD üzerinden bildirilir. OSD tek operasyonel görünürlük kanalıdır; dashboard kapalıyken bile kullanıcı kritik hatayı görür.
- Uygulama mimarisi iki ana role ayrılmıştır:
    1. **Monitoring (Gözlem)**: Dashboard üzerinden detaylı log takibi ve ayarların yapılması.
    2. **Operation (Operasyon)**: OSD üzerinden kayıt/işleme durumu ve kritik hataların takibi.
- **Deterministic Specificity (Belirleyici Spesifiklik)**: Hata mesajları genel ("Hata oluştu") değil, spesifik ("Mikrofon Susturuldu" veya "Cihaz Koptu") olmalıdır. Sistem neden bozulduğunu biliyorsa bunu kullanıcıdan gizlemez.
- Model boyutu ve donanım (CPU/GPU) ayarları `TranscriptionWorker` içindeki yapılandırmaya bağlıdır.
- **Uygulama Dil Seçimi (App Language Selection)**: Desteklenen diller `translations/` dizinindeki JSON dosyalarına göre dinamik olarak listelenir (`core/i18n.py`). Sistem dili çalışma zamanında algılanarak dil listesinin (combobox) en üstünde, dinamik olarak yerelleştirilmiş `(Sistem)` / `(System)` etiketiyle sunulur. Dil seçimi değiştiğinde uygulama yeniden başlatılmaz; `TrayApp.apply_language()` çağrılır, tray menüsü rebuild edilir, Settings dialog kapatılıp yeni dille yeniden açılır (Live UI ilkesi).

## Anti-Patterns ve Yasaklar (Aşırı Mühendisliğe Karşı)
Projenin basitliğini, düz yapısını (flat architecture) ve okunabilirliğini korumak esastır. Bu projeyi geliştiren AI ajanları aşağıdaki pratikleri **KESİNLİKLE dahil etmemelidir**:

1. **Dependency Injection (DI) Framework'leri Yasaktır:** 
   - `injector`, `dependency-injector`, `punq` gibi kütüphaneler veya devasa "Service Container" yapıları kullanılamaz.
   - **Doğrusu:** "Pure DI" (Poor Man's DI) tercih edilmeli. Bağımlılıklar (ör. `SettingsManager`) açıkça obje başlatıcılarına (constructor) bir argüman olarak paslanmalıdır (`settings=settings_manager`).
2. **Global Event Bus / PubSub Mimarileri Yasaktır:**
   - Olaylar için string tabanlı, izlenmesi zor Publisher/Subscriber mekanizmaları kullanılamaz.
   - **Doğrusu:** Tip güvenli (Type-safe) Qt Sinyalleri (Signals) kullanılmalı ve tüm kablolama (wiring) işlemleri explicit (açıkça görünür) bir şekilde `main.py` içerisinde tek bir merkezde yapılmalıdır. Sinyal kablolamasının 100 satır sürmesi, soyutlanmasından daha iyidir (İzlenebilirlik / Traceability).
   - **İstisna:** Loglama sistemi (`logging`), altyapısal bir servis olduğu için bu kuraldan muaftır. Her worker için ayrı sinyal kablolamak yerine, merkezi bir `LoggingHandler` üzerinden "implicit" dağıtım yapılabilir; ancak bu handler'ın başlatılması ve UI bağlantısı `main.py` içinde açıkça (explicit) yapılmalıdır.
3. **Erken Soyutlama (Premature Abstraction):**
   - "Clean Architecture", "SOLID" veya "DRY" kurallarını körü körüne uygulayarak, halihazırda sorunsuz çalışan ve tek dosyada anlaşılan kod bloklarını 5 farklı soyut (abstract) dosyaya parçalamak yasaktır. 
   - **Doğrusu:** Sadece aynı kod 3'ten fazla kez tekrar ederse veya test edilebilirliği kesin olarak engelliyorsa refactor (ayrıştırma) yapılmalıdır.
4. **Asenkron Cehennemi (Asyncio) Yasaktır:**
   - Projeye `asyncio`, `aiohttp`, `qasync` dahil edilerek Event Loop karmaşası yaratılması yasaktır.
   - **Doğrusu:** Arayüzü dondurmamak için bloke edici (blocking) işlemler (örn. model indirme, ağ istekleri, dosya okuma) yerleşik **`QThread`** ve **`Signal/Slot`** yapısı ile arka plana atılmalıdır.
5. **Harici UI Tema Kütüphaneleri Yasaktır:**
   - `qdarktheme`, `qt-material`, `qdarkstyle` gibi "opinionated" ve dışarıdan müdahale edilemez devasa CSS/Stil paketlerinin kurulması yasaktır. 
   - **Doğrusu:** Uygulamanın tasarımı tek bir merkez olan `ui/theme.py` içindeki Design System ile yönetilir. Herhangi bir görsel değişiklik veya modernizasyon standart Qt SSS (Style Sheets) ve paletler kullanılarak manuel olarak yapılmalıdır.
6. **Veritabanı ve ORM Mimarileri Yasaktır:**
   - Basit veri saklama işlemleri için projeye SQLite, SQLAlchemy veya herhangi bir SQL/ORM altyapısı kurmak yasaktır.
   - **Doğrusu:** Konfigürasyon ve basit "state" verileri için projenin mevcut `SettingsManager` (JSON) altyapısı veya düz dosyalar (flat files) kullanılmalıdır. Veritabanı göçleri (migrations) ve karmaşık tablo yapıları getiren sistemler projeye dahil edilmemelidir.
7. **Offline-First ve Gizlilik (Telemetri Yasaktır):**
   - Uygulama, kullanıcının açık rızası (model indirme gibi) dışında hiçbir şekilde internete çıkamaz. Güncelleme kontrolü (update check), telemetri, analitik veya "beacons" gibi arka plan ağ istekleri eklemek kesinlikle yasaktır.
   - **Doğrusu:** Katib bir "air-gapped" araç gibi davranmalıdır. Uygulama güncellemeleri manuel olarak takip edilmeli, kod içerisine otomatik kontrol mekanizmaları kurulmamalıdır.
8. **Aşırı UI Elemanı (Over-UI) ve Minimalist UX (Do What I Mean):**
   - Bir ayarı sıfırlamak veya varsayılana döndürmek için arayüze "Temizle", "Sıfırla" gibi fazladan butonlar veya karmaşık sanal menü öğeleri eklemek (eğer teknik olarak kesinlikle zorunlu değilse) yasaktır.
   - **Doğrusu:** Kullanıcının doğal etkileşimleri değerlendirilmelidir. Örneğin; listelenen bir cihazın yanında "(Varsayılan)" yazıyorsa ve kullanıcı buna tıklıyorsa, amaç "zaten o anki varsayılanı kullanmaktır". Bu eylem arkada ayarı sıfırlamak (implicit state reset) için kullanılmalı, kullanıcıya fazladan bir buton sunulmamalıdır. Arayüz her zaman kompakt (minimalist HUD) kalmalıdır.
