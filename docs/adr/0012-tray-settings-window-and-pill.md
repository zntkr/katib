# ADR-0012: Arayüz = Tepsi Simgesi + Sekmeli Ayar Penceresi + Pill

## Durum
Kabul edildi (2026-10-04). CONTEXT.md'deki "Monitoring = Dashboard" tanımının yerini alır.

## Bağlam
Arayüz dört parçaydı: her zaman üstte duran küçük bir **dashboard** (durum satırı, seviye
çubuğu, mikrofon seçimi, açılır log, son metni kopyala), onun yanına hizalanan iki sütunlu
bir **ayar diyaloğu**, **pill** (OSD) ve tepsi simgesi. Sorunlar:

- **Yarım kalmış "otomatik arayüz".** `core/settings.py`'deki ayar şeması her ayar için beş
  arayüz alanı taşıyordu ve ayar diyaloğunda bu şemadan bileşen üreten genel bir üretici
  vardı. 11 ayardan yalnız 2'sini o üretici çiziyordu; geri kalanı elle kuruluyordu.
  Üreticinin `spinbox`/`doublespinbox` dalları silinmiş ayarlardan kalmaydı, `type_` alanı
  hiç okunmuyordu, bir ayarın seçenekleri iki yerde tanımlıydı, `device_name` ve
  `initial_prompts` şemada yoktu. Yeni ayar eklemenin iki yolu vardı ve hangisinin doğru
  olduğu koddan anlaşılmıyordu.
- **Aynı sinyal iki kez.** Diyalog dashboard'un içinde tembel yaratıldığı için 7 sinyal hem
  diyalogda hem dashboard'da tanımlıydı; dashboard yalnızca aktarıyordu.
- **Üç kopya hizalama kodu** pencereleri dashboard'un yanına yerleştiriyordu.
- Hedef macOS diktesine yakın bir deneyim (ADR-0010): orada da bir simge, yüzen bir gösterge
  ve ayarlar vardır; sürekli açık duran bir pano yoktur.

## Karar
Arayüz üç yüzeyden oluşur:

1. **Tepsi simgesi** (`ui/tray_app.py`): kalıcı durumu simge ve ipucuyla gösterir. Menüsü:
   Ayarlar, Kullanım Kılavuzu, Son metni kopyala, Çıkış. Çift tık Ayarlar'ı açar.
2. **Ayar penceresi** (`ui/settings_window.py`): tek pencere, üç sekme:
   - **Dikte** — dikteyi etkileyen her şey, iki sütun: solda ne duyulduğu (kısayol, konuşma
     dili, mikrofon, seviye çubuğu), sağda neyin yazıya döktüğü (model, komut). Her sütunun
     altında canlı bilgi vardır: son kaydın süresi, konuşma ve taban seviyesi, atıldıysa
     nedeni; modelin GPU'da mı CPU'da mı çalıştığı (GPU kullanılmıyorsa nedeni) ve son
     diktenin kaç saniyede çevrildiği.
   - **Uygulama** — uygulama dili, metin yazma yöntemi, kullanım kılavuzu. (Tema seçimi
     ADR-0013 ile kalktı.)
   - **Günlük** — canlı log.
3. **Pill** (`ui/osd.py`): kayıt, işleme ve hata anında görünür. Solunda bir ses dalgası
   (`LevelWave`) vardır: kayıt sırasında mikrofon seviyesinin son anları sağdan sola akar,
   model çalışırken kendiliğinden dalgalanır, mesaj gösterilirken sabit bir noktadır.
   Seviye dB ölçeğinde çizilir (−60 dB sessizlik, −10 dB tam boy); doğrusal ölçekte kısık
   bir mikrofon hiç kıpırdamıyor görünürdü.

Kurallar:

- **Açılışta hiçbir pencere açılmaz.** Ayar penceresi yalnız kullanıcı isteyince açılır.
  İki istisna: dikte edilecek model yoksa "Dikte" sekmesinde açılır; Windows tepsi
  sunmuyorsa (ör. oturum açılışında Explorer hazır değilken) uygulamaya ulaşmanın ve
  çıkmanın tek yolu olarak açılır. Çıkış düğmesi yalnız bu durumda görünür.
- **Canlı bilgi işçilerden sinyalle gelir**, log satırları ayrıştırılmaz:
  `AudioWorker.recording_analysed`, `TranscriptionWorker.model_loaded` ve `dictation_timed`.
  Pencere son değerleri saklar; `rebuild()` onları yeniden gösterir.
- **Ekranda olmayan ayarlar** (proje sahibinin kararı, 2026-10-04): hassasiyet
  (`compute_type`) ve cihaz (`compute_device`) yalnız `settings.json`'dan değiştirilir;
  "Ayarları Sıfırla" düğmesi ve model yolu satırı kaldırıldı (yol, model bilgisinin ipucunda).
- **Arayüz üreten mekanizma yoktur.** Her sekme kendi `_build_*_tab` metodunda elle kurulur.
  `core/settings.py::DEFAULTS` yalnız ayar adlarını ve varsayılanları tutar; arayüzle ilgili
  hiçbir şey içermez.
- **Pencere tek ve kalıcıdır.** Uygulama açılırken bir kez yaratılır, `main.py`'de bir kez
  bağlanır. Dil değişiminde yeniden yaratılmaz; `rebuild()` sekmeleri yerinde yeniden
  kurar. Böylece sinyal aktarma katmanı gerekmez.
- **Canlı log kalır** (proje sahibinin kararı): teşhis, kullanıcının buradan kopyaladığı
  satırlarla yürüyor.

## Reddedilen Alternatifler
- **Her şeyi şemadan üretmek:** Ekranda görünen ayar sayısı bir düzine bile değil; üretici,
  kazandırdığından fazla karmaşıklık getiriyordu ve her özel durum için ayrıca dal istiyordu.
- **Dashboard'u koruyup yalnız üreticiyi silmek:** Aktarma sinyallerini ve hizalama kodunu
  yerinde bırakırdı.
- **Dil değişince pencereyi yok edip yeniden yaratmak (eski davranış):** Pencere `main.py`'de
  bağlandığı için her yeniden yaratmada bağlantıların da yeniden kurulması gerekirdi.

## Sonuçlar
- Yeni ayar eklemenin tek yolu CONTEXT.md → Geliştirici Notları'nda yazılıdır.
- `SettingsWindow`'un her public sinyali `main.py`'de bağlı olmalıdır
  (`tests/test_signal_wiring.py`).
- ADR-0008 geçerliliğini korur: model seçimi mantığı ayar penceresinin dosyasında kalır.
- Davranış değişiklikleri (bilinçli):
  - İndirilen model artık kalıcı olarak seçilir (`model_dir` yazılır); eskiden yalnız o
    oturumda kullanılıyor, yeniden başlatınca eski modele dönülüyordu.
  - Otomatik dil algılamadayken kaydedilen komut artık `initial_prompts`'a `"null"`
    anahtarıyla yazılmaz.
  - Varsayılan `model_dir` (modeller kökü) model listesinde "Özel: Models" girdisi olarak
    görünmez.
  - "Son metni kopyala" tepsi menüsündedir; ayrıca her dikte "Günlük" sekmesinde durur.
  - Model listesinde yalnız ad ve boyut yazar; "Slow / Very Slow" gibi hız açıklamaları
    GPU ile yanlış kaldığı için gösterilmez.
- Worker'ların `status_changed` sinyalindeki ikinci alan (seviye: `OK`/`WARN`/`IDLE`…) artık
  hiçbir yerde gösterilmiyor; sinyal imzası bu ADR'nin kapsamında değiştirilmedi.
- İkinci kez başlatılan Katib hâlâ sessizce kapanır; çalışan kopyanın ayar penceresini
  açması istenirse ayrı iş olarak ele alınmalıdır.
