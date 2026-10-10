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
5. İşe başlamadan **açık planlara** bak: `docs/plans/README.md`. İş bir plana bağlıysa planın "Devralma notu"ndan başla; plan kendi kendine yeten devir belgesidir. Yeni bir tarama/incelemeye başlamadan önce mevcut tarama belgelerini oku (`docs/*-incelemesi-*.md`) — bilinen bulguyu yeniden keşfetme.
6. Bulduğun ve hemen düzeltmeyeceğin her kusur önce bir tarama belgesine (kanıtıyla), sonra numaralı bir plana düşer. Plan yazma kuralları: `docs/plans/README.md` → "Plan yazma kuralları".

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
- **Theme Manager**: Uygulamanın tek renk paletini (koyu mavimsi gri; açık tema yoktur, ADR-0013) ve stil dosyasını tutan merkezi birim (`ui/theme.py`). Bileşenler rengi yalnız buradan alır.
- **OSD (Status Indicator)**: Katib esnasında ekranın alt-ortasında beliren, etkileşimsiz (click-through) ve minimalist durum göstergesi. Kayıt/işleme durumu ve kritik hataların tek operasyonel görünürlük kanalıdır.
- **Armored Logic (Zırhlı Mantık)**: İşçi (Worker) seviyesinde başlayan, sistem hatalarını (örn. Mute durumu) proaktif olarak tespit edip kullanıcıyı uyaran korumacı mühendislik katmanı.
- **Binary Armor (İkili Zırh)**: "Ölü veya Canlı" prensibi. Sinyal matematiksel olarak tam sıfır (0.0) ise hata (Mute) kabul edilir; 0.0'dan büyük her sinyal (fısıltı dahil) geçerli kabul edilerek işlenir.
- **GPU Hızlandırma (isteğe bağlı)**: Whisper modeli, kullanılabilir bir NVIDIA GPU ve CUDA kitaplıkları varsa GPU'da, yoksa CPU'da çalışır. GPU bir iyileştirmedir, gereksinim değildir: yüklemede, ısınmada ya da dikte anında GPU hata verirse Katib CPU'ya döner ve çalışmaya devam eder. Kararı yalnız `core/gpu.py` verir; kullanıcı `compute_device` ayarıyla (`auto` / `cpu` / `cuda`) zorlayabilir. Bkz. ADR-0010, plan 0009.
- **Zombie Device (Hayalet Cihaz)**: Fiziksel bağlantısı kesilmiş olmasına rağmen PortAudio'nun (ve Windows sürücüsünün) hâlâ listelemaya devam ettiği mikrofon. `sd.query_devices()` cihazı gösterir, ancak `sd.InputStream` açılmaya çalışıldığında PortAudio hatası (-9996 / Invalid device) fırlatır. `QMediaDevices.audioInputs()` (Qt) ve `sd.query_devices()` (PortAudio) farklı isim formatları kullandığından iki liste arasında güvenilir isim eşleştirmesi yapılamaz. Bkz. ADR-0007.

## Mimari Kurallar
1. **Thread Güvenliği**: UI bileşenlerine doğrudan diğer thread'lerden erişilemez. Tüm iletişim Qt Sinyalleri (Signals) üzerinden yapılmalıdır.
2. **Heavy Operations**: Model yükleme, ses işleme ve disk işlemleri asla ana thread'de (UI thread) yapılmaz.
   - **Bilinen istisna:** Worker'lar `QThread` alt sınıfıdır ve nesneleri ana thread'de yaşar; bu yüzden `AudioWorker`'ın slot'ları (`start_recording`, `stop_recording`, `refresh_devices`) ana thread'de çalışır. Süreleri `@measure_time` ile loglanır ("UI thread" etiketiyle). Windows ölçümleri 100 ms'yi aşarsa `AudioWorker` gerçek bir worker thread'e taşınmalıdır; tüm PortAudio çağrıları o zaman tek bir thread'de toplanmalıdır.
   - PortAudio callback'lerinin (`_audio_callback`, `_on_stream_finished`) içinden PortAudio'yu yeniden başlatan veya stream kapatan hiçbir çağrı yapılmaz (bkz. ADR-0007).
3. **Single Instance**: Uygulama aynı anda sadece bir kez çalışabilir (`QSharedMemory("Katib_SingleInstance_Mutex")` ile kontrol edilir).
4. **Graceful Shutdown**: Uygulama kapanırken worker'lar belirli bir sırayla (Hotkey -> Audio -> Transcription) durdurulur ve OS seviyesinde `os._exit(0)` ile temiz kapanış yapılır.
5. **Event Debouncing (Olay Susturma)**: İşletim sistemi kaynaklı donanım sinyalleri (ör. `QMediaDevices` mikrofon tak-çıkar uyarıları) bazen saniyede onlarca kez tetiklenerek bir "Event Storm" (sinyal fırtınası) yaratabilir. Bu tarz donanımsal veya yoğun GUI sinyallerini yakalarken doğrudan Worker'ları veya ağır işlemleri tetiklemek yerine, mutlaka `QTimer` kullanılarak **Debounce** (geciktirme/filtreleme) mantığı kurulmalıdır. Sinyaller yatışana kadar (ör. 500ms) beklenmeli ve işlem sadece 1 kez yapılmalıdır.
6. **Live UI ve State Yönetimi**: Ayarlar ekranındaki etkileşimler anında (Live) uygulanmalıdır. Uzun metin girişleri (örn. QLineEdit) için I/O spamını önlemek adına "Kaydet" butonu eklenebilir, ancak pencere kapanırken "Kaydetmeden Çıkıyorsunuz" gibi kullanıcıyı bloke eden (blocking modal) uyarılar **kesinlikle yasaktır**. Değişiklik yokken "Kaydet" butonunun pasif (disabled) yapılması, durum yönetimi (State) için yeterli ve doğru geri bildirimdir.
7. **Güvenli Kapanış ve Bellek Yönetimi (UI Teardown)**: Tüm üst düzey arayüz bileşenleri (Pencereler, OSD, Dialoglar), `closeEvent` metodunu ezerek içerdikleri aktif `QTimer` ve `QPropertyAnimation` nesnelerini (`findChildren` aracılığıyla) manuel olarak durdurmalıdır. Özellikle "Event Debouncing" kaynaklı zamanlayıcıların C++ belleğinde asılı kalıp test süreçlerini (Pytest) bozmasını önlemek için bu "explicit cleanup" zorunludur.
8. **Kullanıcı Verisi Değişikliği Onay İster**: Kullanıcının diskte kalıcı duran verisinin yapısını veya yerini değiştiren her iş, planlama aşamasında proje sahibinden **açık onay** alır. Mevcut kullanıcıların dosyası ya da klasörü yeni yapıda yanlış okunacaksa iş **taşıma (migration) kodu** da içerir; taşıma hiçbir durumda uygulamayı çökertmez. Kapsam:
   - `settings.json`: anahtar adı değiştirme/silme, değer tipini ya da anlamını değiştirme, varsayılanı değiştirme (yalnız varsayılandan farklı değerler kaydedildiği için yeni varsayılan mevcut kullanıcılara da ulaşır), dosyanın yeri.
   - Uygulama veri klasörleri: kök (`get_app_data_dir()`), `Models\` ve `Logs\` düzeni, model klasör adları (kurumsal kılavuz bunlara bağlı).
   - **Kapsam dışı:** yeni bir ayar anahtarı eklemek (varsayılanıyla, `core/settings.py` şemasından) onay istemez.
   - Örnek: `~/.katib_app` → `%LOCALAPPDATA%\Katib` taşıması (ADR-0009, `migrate_legacy_data()`). Her planın başlığında "Kullanıcı verisi değişikliği: YOK/VAR" satırı bu kuralı görünür kılar (`docs/plans/README.md`).

## Dosya Yapısı ve Sorumluluklar
- `main.py`: Uygulamanın giriş noktası ve sinyal yönlendirme merkezi.
- `ui/`: Arayüzün üç yüzeyi (ADR-0012): tepsi simgesi (`tray_app.py`), sekmeli ayar penceresi (`settings_window.py`) ve pill (`osd.py`); ayrıca kullanım kılavuzu penceresi.
- `workers/`: İş mantığını yürüten arka plan thread'leri.
- `core/`: Ayarlar, metin enjeksiyonu ve tema gibi çekirdek yardımcı işlevler.
- `ui/osd.py`: Operasyonel geri bildirim için kullanılan minimalist gösterge katmanı.
- `tests/`: Uygulamanın stabilitesini ölçen birim ve entegrasyon testleri.

## Dosya Konumları (Çalışma Zamanı Verisi)
Tüm uygulama verisi tek bir kökte tutulur (ADR-0009). Kök yalnızca `core/settings.py::get_app_data_dir()` içinde hesaplanır:

- Kök: `%LOCALAPPDATA%\Katib` (Linux: `$XDG_DATA_HOME/Katib`, varsayılan `~/.local/share/Katib`)
- Ayarlar: `<kök>\settings.json` — `get_settings_path()`
- Modeller: `<kök>\Models\<model-klasörü>` — `DEFAULT_DOWNLOAD_PARENT`. Klasör adı `repo_id`'nin son parçasıdır (örn. `faster-whisper-small`).
- Loglar: `<kök>\Logs\katib.log` — `get_log_dir()`
- Eski konum `~/.katib_app`, açılışta `migrate_legacy_data()` ile taşınır.
- **Program dosyaları veri kökünde durmaz (ADR-0014):** kurulum her zaman `%LOCALAPPDATA%\Programs\Katib` klasörüne yapılır (klasör sorulmaz) ve kaldırıcı yalnız kendi kurduğunu kaldırır. Betiğe veri köküne yazan ya da oradan silen satır eklenmez (`tests/test_installer.py`). 1.0.0 programı veri köküne kuruyordu (plan 0011).

## Geliştirme Ortamı (ADR-0011)
Python sürümü tek yerde yazar: `.python-version`. CI ve `build.bat` oradan okur. Her şey projenin kendi sanal ortamında çalışır; genel Python ortamından çalıştırma ve derleme desteklenmez (makinede birden çok Python kurulu olabilir ve `python` komutu yanlışına gidebilir).

```
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt -c constraints.txt
.venv\Scripts\python -m pytest -q
.venv\Scripts\python main.py
build.bat                      # ortamı kurar/eşitler, PyInstaller ve Inno Setup'ı çalıştırır
build.bat gpu                  # aynısı + NVIDIA cuBLAS: Katib_Setup_<sürüm>_GPU.exe (plan 0009 Faz 2)
```

- Bağımlılıklar sabittir: doğrudan olanlar `requirements*.txt` içinde `==` ile, çektikleri her paket `constraints.txt` içinde. Sürüm değiştirirken ikisi birlikte güncellenir (adımlar: ADR-0011 → Sonuçlar).
- GPU ile denemek için ayrıca: `.venv\Scripts\python -m pip install -r requirements-gpu.txt` (ADR-0010).
- `build.bat` PyInstaller'ı yalnız Windows klasörleri PATH'teyken çalıştırır ve `Katib.spec` hiçbir `icu*.dll`'i pakete almaz: derleyen bilgisayardaki araçların DLL'leri (ör. Poppler'ın ICU'su) pakete sızınca Qt açılışta düştü. Qt, Windows'un kendi ICU'sunu kullanır (plan 0015).
- Derlemenin istediği her dosya depoda olmalıdır (`hooks/`, `Katib.iss`). `.gitignore`'a bir şey eklemeden önce `Katib.spec` ve `build.bat`'ın onu isteyip istemediğine bak.

## Geliştirici Notları
- **Yeni ayar eklemenin tek yolu:** (1) `core/settings.py::DEFAULTS`'a anahtarı ve varsayılanını yaz; (2) ekranda görünecekse bileşenini `ui/settings_window.py`'de ilgili sekmenin `_build_*_tab` metoduna **elle** ekle ve `_refresh_values`'a işle. Ayar listesinden arayüz üreten bir mekanizma yoktur ve kurulmamalıdır (ADR-0012). `tests/test_config.py`, kodda okunan her anahtarın `DEFAULTS`'ta olduğunu denetler.
- Kullanıcıya gösterilecek operasyonel hatalar OSD üzerinden bildirilir (worker'ların `error_occurred` sinyali `main.py`'de `osd.setStateError`'a bağlıdır). OSD tek operasyonel görünürlük kanalıdır; hiçbir pencere açık değilken bile kullanıcı kritik hatayı görür.
- Worker'ların her public sinyali `main.py`'de bağlanmalıdır; `tests/test_signal_wiring.py` bağlanmamış bir sinyali yakalar. Kullanılmayan bir sinyal eklemek yerine silinmelidir.
- Ayar penceresi (`SettingsWindow`) uygulama boyunca yaşayan tek nesnedir ve `main.py`'de bir kez bağlanır; her public sinyali `main.py`'de bağlı olmalıdır (test ile korunur). Dil değişince pencere yeniden yaratılmaz, sekmeleri yerinde yeniden kurulur (`rebuild()`), böylece bağlantılar kopmaz.
- `main.py` ve `TrayApp` ayar penceresinin `_` ile başlayan üyelerine erişmez; yalnızca public metotlarını kullanır (test ile korunur).
- Tepsi simgesini ve ipucunu yalnızca `TrayApp._resolve_status()` yazar. Worker'lar olgu bildirir (`status_changed`, `transcription_started/finished`, `mic_unavailable`), `TrayApp` tek öncelik kuralıyla karar verir: kayıt > işleme > indirme bildirimi > mikrofon yok > model durumu. `main.py` tepsi ipucunu ya da simgesini kendisi yazmaz (test ile korunur).
- Arayüz iki role ayrılmıştır (ADR-0012):
    1. **Monitoring (Gözlem)**: Ayar penceresi, üç sekme: "Dikte" (kısayol, konuşma dili, mikrofon, model, komut ve canlı bilgi: son kaydın seviyesi, modelin çalıştığı yer, son diktenin süresi), "Uygulama" (dil, yazma yöntemi) ve "Günlük" (canlı log). Kendiliğinden açılmaz; tepsi menüsünden açılır. Tek istisnalar: dikte edilecek model yoksa "Dikte" sekmesinde açılır, Windows tepsi sunmuyorsa uygulamaya ulaşmanın tek yolu olarak açılır.
    2. **Operation (Operasyon)**: OSD (pill) üzerinden kayıt/işleme durumu ve kritik hataların takibi; tepsi simgesi ve ipucu kalıcı durumu gösterir.
- **Deterministic Specificity (Belirleyici Spesifiklik)**: Hata mesajları genel ("Hata oluştu") değil, spesifik ("Mikrofon Susturuldu" veya "Cihaz Koptu") olmalıdır. Sistem neden bozulduğunu biliyorsa bunu kullanıcıdan gizlemez.
- Modelin hangi donanımda çalışacağını `TranscriptionWorker._open_model` seçer: önce GPU (`core/gpu.py` "kullanılabilir" diyorsa), olmazsa CPU. GPU'ya dokunan her yeni kod yolu CPU'ya dönüşünü ve testini de getirir (ADR-0010). `compute_type` ayarı yalnız CPU içindir; GPU'da hesap tipi otomatik seçilir.
- **Tek tuş, iki dikte (plan 0014)**: tuş basılı tutulursa metin bırakışta tek seferde yapıştırılır (basılı tuşun yanında gönderilen Ctrl+V başka bir kısayola dönüşür). Tuşa kısa dokunulursa (< 0,8 sn) dikte eller serbest sürer: ikinci dokunuşta ya da 3 sn sessizlikte biter ve bölümler konuşurken, duraklamada yazılır. Bölüm, en az 0,7 sn'lik bir duraklamada kesilir; duraklamadan önce CPU'da en az 8 sn, GPU'da en az 1,5 sn ses olmalıdır (`core/segmenter.py`; GPU'da bir bölüm 0,2–0,4 sn sürdüğü için). GPU'da konuşma duraklamadan sürerse bekleyen sesin tamamı çözümlenir ve içindeki ilk bitmiş cümle, iki ardışık geçişte aynı sözcüklerle çıkarsa yazılır (`TranscriptionWorker._type_finished_sentence`); duraklama kuralı önceliklidir, çünkü daha hızlıdır. Cümlenin sonu modelin bölümlerinden değil sözcüklerinden bulunur (`core/segmenter.py::first_sentence`): duraklamasız konuşmada model her şeyi tek bölüm döndürür. Sözcük sözcük canlı yazma denendi ve alınmadı (plan 0014): Whisper'la söylenenin 5 sn gerisinde kalıyor. Art arda yapıştırmalarda kullanıcının panosu bir kez yedeklenir ve son yapıştırmadan sonra bir kez geri konur (`core/text_injector.py`).
- **GPU modeli yok edilmez**: GPU'da çalışmış bir CTranslate2 modelini yok etmek süreci öldürebilir (plan 0009, 2026-10-10). Model değiştirirken ve CPU'ya dönerken `TranscriptionWorker._release_model` GPU modelinin belleğini `unload_model()` ile boşaltır ve nesneyi tutar; Katib `os._exit` ile çıktığı için yıkıcı hiç çalışmaz. GPU modeline `del` ya da `= None` ile veda eden yeni bir yol eklenmez. GPU'ya dokunan her değişiklikten sonra gerçek kartta `scripts/gpu_model_degisimi.py` çalıştırılır.
- Testler makinenin GPU'suna bağlı olamaz: `tests/conftest.py::_no_gpu` GPU'yu varsayılan olarak kullanılamaz yapar; GPU davranışını sınayan test `core.gpu`'yu kendisi yamalar.
- **Model listesi tek iş görür**: Kapalı liste her zaman kullanımdaki modeli gösterir (hiç model yoksa "Model seçin"). Her satır durumunu sözle söyler: `faal`, `indirildi`, `indir (1.5 GB)`, `indiriliyor`. İndirilmiş satırı seçmek modeli hemen değiştirir; indirilmemiş olanı seçmek indirmeyi sorar ve liste kullanımdaki modele geri döner. Boyutlar gerçektir: `WHISPER_MODELS[...]["bytes"]` deponun tüm dosyalarının toplamıdır ve liste, indirme ilerlemesi ve kılavuz onu `format_size()` ile gösterir; başka yere boyut yazılmaz. Ayrı bir indirme düğmesi yoktur ve eklenmemelidir (yasak 8). Aynı anda tek indirme olur. `selected_model_repo` ayarı artık okunmuyor ve yazılmıyor; anahtarı silmek kural 8 gereği proje sahibinin onayını bekliyor.
- **Model indirme ilerlemesi**: `ModelDownloaderWorker.download_progress` (inen bayt, beklenen bayt, bayt/sn) ayar penceresindeki çubuğu doldurur ve hemen altına `Medium · indiriliyor · 0.4 / 1.5 GB · 6.1 MB/s` yazar (toplam, listedeki gerçek boyuttur); kullanımdaki modelin satırları onun altında kalır (GPU notu indirme hatası gibi okunmasın). Hız son 5 saniyenin ortalamasıdır. Bilgi `huggingface_hub`'dan gelir: `snapshot_download(tqdm_class=...)` ve hız sıçramasın diye 1 MB'a çekilen iç sabit `constants.DOWNLOAD_CHUNK_SIZE` (varsayılan 10 MB). İkisi de kütüphanenin elindedir: kaybolurlarsa indirme çalışmaya devam eder, yalnız çubuk belirsiz hâline döner ya da hız sıçrar. Sürüm yükseltirken bunu `tests/test_model_downloader_worker.py::TestLibraryContract` yakalar.
- **İlk açılışta konuşma dili**: Yeni kurulumda (açılışta `settings.json` yoksa, `SettingsManager.first_run`) konuşma dili bilgisayarın diline ve o dilin hazır prompt'una ayarlanır; dil `SPEECH_LANGUAGES`'ta yoksa otomatik algılama kalır (İngilizceye düşülmez). Mevcut kullanıcıların ayarına dokunulmaz; `DEFAULTS["language"]` `auto`'dur. Bkz. plan 0012 Faz 5.
- **Uygulama Dil Seçimi (App Language Selection)**: Desteklenen diller `translations/` dizinindeki JSON dosyalarına göre dinamik olarak listelenir (`core/i18n.py`). Sistem dili çalışma zamanında algılanarak dil listesinin (combobox) en üstünde, dinamik olarak yerelleştirilmiş `(Sistem)` / `(System)` etiketiyle sunulur. Dil seçimi değiştiğinde uygulama yeniden başlatılmaz; `TrayApp.apply_language()` çağrılır, tray menüsü yeniden kurulur ve ayar penceresinin sekmeleri yeni dille yerinde yeniden kurulur (Live UI ilkesi).

## Anti-Patterns ve Yasaklar (Aşırı Mühendisliğe Karşı)
Projenin basitliğini, düz yapısını (flat architecture) ve okunabilirliğini korumak esastır. Bu projeyi geliştiren AI ajanları aşağıdaki pratikleri **KESİNLİKLE dahil etmemelidir**:

1. **Dependency Injection (DI) Framework'leri Yasaktır:** 
   - `injector`, `dependency-injector`, `punq` gibi kütüphaneler veya devasa "Service Container" yapıları kullanılamaz.
   - **Doğrusu:** "Pure DI" (Poor Man's DI) tercih edilmeli. Bağımlılıklar (ör. `SettingsManager`) açıkça obje başlatıcılarına (constructor) bir argüman olarak paslanmalıdır (`settings=settings_manager`).
2. **Global Event Bus / PubSub Mimarileri Yasaktır:**
   - Olaylar için string tabanlı, izlenmesi zor Publisher/Subscriber mekanizmaları kullanılamaz.
   - **Doğrusu:** Tip güvenli (Type-safe) Qt Sinyalleri (Signals) kullanılmalı ve tüm kablolama (wiring) işlemleri explicit (açıkça görünür) bir şekilde `main.py` içerisinde tek bir merkezde yapılmalıdır. Sinyal kablolamasının 100 satır sürmesi, soyutlanmasından daha iyidir (İzlenebilirlik / Traceability).
   - **İstisna:** Loglama sistemi (`logging`), altyapısal bir servis olduğu için bu kuraldan muaftır. Her worker için ayrı sinyal kablolamak yerine, `core/log.py` üzerinden "implicit" dağıtım yapılır: bileşenler `get_logger("MIC")` gibi `Katib.<BİLEŞEN>` logger'ı kullanır; dosya handler'ı `setup_logging()` (yazma `QueueListener` thread'inde; kapanışta `stop_logging()`), ayar penceresinin "Günlük" sekmesini besleyen handler (`LogViewHandler`) `main.py` içinde açıkça (explicit) kurulur. Dikte edilen metin mesaja gömülmez, `extra={"transcript": metin}` ile verilir: "Günlük" sekmesi metni gösterir, diske yalnızca uzunluğu yazılır (ADR-0004).
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
