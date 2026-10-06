# Plan 0010 — Tek Pencereli Arayüz (dashboard'un kaldırılması)

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **DOĞRULAMA BEKLİYOR** — Faz 1–3 bitti (2026-10-04, `feat/tabbed-settings-window`
dalının çalışma ağacında, commit edilmedi); Faz 4 proje sahibinin gerçek uygulamada denemesini bekler.
**Kullanıcı verisi değişikliği:** YOK — `settings.json`'ın anahtarları, varsayılanları ve yeri
aynı. `device_name` ve `initial_prompts` zaten kullanılıyordu; yalnız ayar listesine yazıldılar.
İndirilen modelin `model_dir`'e yazılması davranış düzeltmesidir (ADR-0012 → Sonuçlar).
**Öncelik:** 🟠 Orta-yüksek — ayar eklemenin iki yolu vardı ve hangisinin doğru olduğu koddan
anlaşılmıyordu; her arayüz değişikliği bu belirsizliğe takılıyordu.
**Tarih:** 2026-10-04
**İlgili belgeler:** ADR-0012 (karar ve gerekçe), ADR-0008, CONTEXT.md → "Geliştirici Notları"

---

## Neden bu plan

Kanıtlar ADR-0012 → Bağlam'da. Kısaca: ayar şemasından arayüz üreten yarım bir mekanizma
(11 ayardan 2'sini çiziyordu), dashboard ile ayar diyaloğu arasında iki kez tanımlanan 7 sinyal
ve pencereleri dashboard'un yanına hizalayan üç kopya kod. Proje sahibi arayüzün tepsi simgesi,
tek bir sekmeli ayar penceresi ve pill ile sınırlanmasını istedi.

---

## Devralma notu

```bash
# Faz 1–3 BİTTİYSE: tek pencere var, eski iki dosya yok
ls ui/settings_window.py
ls ui/dashboard.py ui/settings_dialog.py        # ikisi de "yok" demeli
grep -n "SETTINGS_SCHEMA\|SettingDef" -r core ui workers tests   # çıktı boş
python -m pytest -q tests/test_settings_window.py tests/test_tray_app.py tests/test_signal_wiring.py
# Faz 4 BAŞLAMADIYSA: Yürütme günlüğünde "gerçek uygulamada denendi" satırı yok
```

**Ortam:** `.venv` (ADR-0011). Testler tepsiye ve makinedeki modellere bağlı değildir:
tepsi varlığı ve modeller klasörü testlerde yamalanır.

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Canlı log | "Günlük" sekmesinde kalır | Proje sahibinin kararı (2026-10-04): teşhis oradan kopyalanan satırlarla yürüyor |
| Açılış | Hiçbir pencere açılmaz; yalnız tepsi simgesi. Model yoksa Ayarlar "Model" sekmesinde açılır | Proje sahibinin kararı (2026-10-04) |
| Tepsi yoksa | Ayar penceresi açılır; "Genel" sekmesinde Çıkış düğmesi var | Açılışta pencere olmayınca, tepsisiz durumda uygulamaya ulaşmanın başka yolu kalmıyordu |
| Arayüz üretici | Silindi; her sekme elle kurulur | ADR-0012 |
| Ayar listesi | `DEFAULTS` sözlüğü: yalnız anahtar ve varsayılan | Arayüz alanları artık kimse tarafından okunmuyor |
| Pencere ömrü | Tek nesne, açılışta yaratılır, `main.py`'de bağlanır; dil değişince `rebuild()` | Sinyal aktarma katmanını gereksiz kılar |
| Renkler | Tek palet: koyu mavimsi gri; açık tema ve tema seçimi yok | Proje sahibinin kararı (2026-10-04), ADR-0013 |
| Durum satırı | Pencerede yok; tepsi ipucu ve pill gösterir | İkisi zaten aynı bilgiyi veriyordu |
| Son metni kopyala | Tepsi menüsünde | Dashboard'daki düğmenin yerine |
| `status_changed`'in seviye alanı | Dokunulmadı (artık gösterilmiyor) | Sinyal imzasını değiştirmek worker testlerine yayılır; ayrı iş |
| Sekme sayısı | Üç: Dikte, Uygulama, Günlük | Proje sahibinin kararı (2026-10-04): beş sekmeye dokuz kontrol dağılmıştı |
| Canlı bilgi | Son kaydın seviyesi; modelin çalıştığı yer ve son diktenin süresi | Proje sahibinin kararı; 3 Ekim'deki mikrofon teşhisinde logdan okunan her şey buydu |
| Ekrandan kalkanlar | Hassasiyet seçimi, "Ayarları Sıfırla", model yolu satırı; Çıkış düğmesi yalnız tepsi yokken | Proje sahibinin kararı; ayarların kendisi `settings.json`'da duruyor |
| Canlı bilginin kaynağı | İşçilerden yeni sinyaller (`recording_analysed`, `dictation_timed`, `model_loaded` argümanları) | Log satırı ayrıştırmak kırılgan olurdu |

---

## Faz 1 — Sekmeli ayar penceresi

- [x] `ui/settings_window.py`: önce beş sekme (Genel, Ses, Model, İşlem, Günlük), aynı gün
      üç sekmeye indirildi (Dikte, Uygulama, Günlük); her biri `_build_*_tab`.
- [x] `core/settings.py`: `SettingDef`/`SETTINGS_SCHEMA` → `DEFAULTS`, `PROCESSING_KEYS`,
      `SPEECH_LANGUAGES`, `INJECTION_METHODS`.
- [x] Çeviriler (11 dil): `dashboard.*` ve `schema.*` bölümleri kalktı; yaşayan metinler
      `settings.*` ve `tray.menu.*` altına taşındı; üç yeni metin (`group_audio`, `group_log`,
      `microphone_label`); `help.trouble_desc1` yeni yere göre yeniden yazıldı.

## Faz 2 — Mikrofon, log ve tepsinin taşınması

- [x] Mikrofon listesi ve seviye çubuğu "Ses" sekmesine; log "Günlük" sekmesine.
- [x] `TrayApp`: pencerenin sahibi; menüde "Son metni kopyala"; açılışta pencere yok;
      tepsi yoksa pencere açılır; kayıt bittikten sonra gelen seviye sinyali düşürülür.
- [x] `main.py`: bağlantılar doğrudan `SettingsWindow`'a; açılışta pencere gösterilmez.

## Faz 3 — Dashboard'un silinmesi

- [x] `ui/dashboard.py`, `ui/settings_dialog.py` ve testleri silindi.
- [x] Kalıntılar: `get_dwm_visual_bounds`, tema içindeki dashboard kuralları ve sabitleri,
      `DashboardLogHandler` → `LogViewHandler`.
- [x] CONTEXT.md ve ADR-0012.

## Faz 4 — Gerçek uygulamada doğrulama (proje sahibi)

- [ ] Uygulamayı `.venv\Scripts\python main.py` ile aç. Beklenen: hiçbir pencere açılmaz,
      tepsi simgesi görünür, F9 ile dikte çalışır.
- [ ] Tepsi → Ayarlar: üç sekme; mikrofon değiştir, dili değiştir. Renkler göze nasıl
      geliyor (koyu mavimsi gri, ADR-0013)?
- [ ] Bir dikteden sonra "Dikte" sekmesinde "Son kayıt" ve "Son dikte" satırları doluyor mu;
      model satırı GPU/CPU'yu doğru gösteriyor mu.
- [ ] "Günlük" sekmesinde dikte satırları görünüyor mu; tepsi → "Son metni kopyala" çalışıyor mu.
- [ ] `build.bat` ile derlenen sürümde aynı kontroller.

---

## Bilinçli olarak YAPILMAYACAKLAR

- **İkinci kez başlatılan Katib'in çalışan kopyanın ayar penceresini açması.** İstenirse ayrı iş.
- **`status_changed` sinyalinden seviye alanını çıkarmak.** Worker testlerine yayılır.
- **Ayar penceresini birden çok dosyaya bölmek.** ADR-0008.

## Test stratejisi

- `tests/test_settings_window.py` (75 test fonksiyonu): pencere, yeniden kurulum, kısayol,
  mikrofon, son kayıt bilgisi, model bilgisi, model listesi, konuşma dili ve komut, log.
- `tests/test_tray_app.py` (44): açılış, menü, dikte, durum önceliği, dil değişimi, tepsisiz durum.
- `tests/test_audio_worker.py::TestRecordingAnalysed` (4) ve
  `tests/test_transcription_worker_logic.py::TestModelLoadedReport` (6), `::TestDictationTimed` (2):
  canlı bilgiyi taşıyan sinyaller.
- `tests/test_signal_wiring.py`: ayar penceresinin her public sinyali `main.py`'de bağlı.
- `tests/test_config.py`: kodda okunan her ayarın `DEFAULTS`'ta varsayılanı var.
- Pencere ve tepsi testleri onları kullanıcı gibi kullanır (bileşenler, public metotlar,
  sinyaller); özel üyeye erişim sıfır. Tüm takımda özel üye erişimi 331'den 218'e indi
  (worker testleri mevcut üslupla yazıldı ve hâlâ özel metotları çağırıyor).

⚠️ **Plandan sapma — testler önce yazılmadı.** Pencere eski iki dosyadan taşınarak yazıldı,
testler ardından geldi. **Kırmızı kanıtı** bu yüzden geriye dönük alındı: sekiz davranış tek
tek geri alındı ve her seferinde ilgili test kırmızıya döndü (otomatik dilde komutun dile
yazılmaması, indirilen modelin kalıcı seçilmesi, yeniden kurulumda mikrofonun yeniden
bildirilmemesi, listenin kullanılan modeli göstermesi, açılışta pencere açılmaması, geç gelen
seviyenin düşürülmesi, sinyal bağlantısı denetimi, varsayılan denetimi).

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| Açılışta hiçbir şey görünmediği için kullanıcı uygulamanın açıldığını anlamaz | Orta | Faz 4'te değerlendirilir; gerekirse açılışta pill kısa süre gösterilebilir |
| Eski testlerin koruduğu bir davranış taşınırken kayboldu | Orta | Durum önceliği testleri birebir taşındı; Faz 4 elle doğrular |
| 11 dildeki yeni metinler anadili gözüyle denetlenmedi | Düşük | Kısa etiketler; mevcut metinlerin kalıbı izlendi |

## Efor

Faz 1–3: yapıldı · Faz 4: 15 dk (proje sahibi)

---

## Yürütme günlüğü

### 2026-10-04 — Faz 1–3 uygulandı

Dashboard (536 satır) ve ayar diyaloğu (629 satır) silindi; yerlerine tek `ui/settings_window.py`
geldi. İzlenen dosyalarda 679 satır eklendi, 3.610 satır silindi.

**Testler (`.venv`):** 601 geçti, kırmızı yok. (Önce 667: silinen iki pencerenin testleri
gitti, yerlerine davranışı koruyan daha az sayıda test geldi.)

**Görsel kontrol:** beş sekme koyu ve açık temada ekran görüntüsüyle incelendi; yerleşim düzgün.

**Bağlantı kontrolü:** `main.py`'nin `window.` ve `tray.` üzerinden eriştiği her üyenin
sınıfta var olduğu ayrıca denetlendi.

⚠️ **Denenmedi:** uygulamanın gerçekten çalıştırılması (proje sahibinin Katib'i açıktı; ikinci
kopya açılmıyor), derlenmiş sürüm, sağdan sola diller, tepsinin gerçekten bulunmadığı bir oturum.

### 2026-10-04 — Üç sekmeye indirildi, canlı bilgi eklendi

Proje sahibi sekmelerin daha yoğun ve kullanışlı olmasını, gereksizlerin elenmesini istedi ve
üç kararı verdi (Kararlar tablosunun son dört satırı). Beş sekme üçe indi; "Dikte" sekmesi iki
sütunlu ve her sütunun altında canlı bilgi var. Pencere 600×340.

- İşçilere eklenenler: `AudioWorker.recording_analysed(süre, konuşma dB, taban dB, neden)`;
  `TranscriptionWorker.dictation_timed(ses süresi, geçen süre)`; `model_loaded` artık cihazı,
  hesap tipini ve GPU'nun neden kullanılmadığını taşıyor.
- Kaldırılanlar: hassasiyet seçimi, "Ayarları Sıfırla" (ve `reset_processing_settings`),
  model yolu satırı, `model_reload_requested` sinyali; model listesindeki hız açıklamaları.
- Çeviriler: iki sekme adı ve iki bilgi satırı eklendi (11 dil); "Ayarlar → Genel/İşlem/Ses/Model"
  diyen beş yardım metni "Ayarlar → Dikte" olacak şekilde güncellendi; kullanılmayan sekiz
  anahtar silindi.

**Testler (`.venv`):** 622 geçti, kırmızı yok. **Kırmızı kanıtı** yine geriye dönük: sekiz
davranış geri alındığında ilgili testler kırmızıya döndü.

**Görsel kontrol:** koyu temada "her şey yolunda", açık temada "kayıt çok kısık + GPU
kitaplığı yok" senaryoları ekran görüntüsüyle incelendi.

### 2026-10-04 — Pill'e ses dalgası

Proje sahibi pill'de dinamik bir ses dalgası istedi; biçimi serbest bıraktı. Pill'deki nokta
`LevelWave` ile değişti (ADR-0012 → Karar 3). Bu kez testler önce yazıldı
(`tests/test_osd.py`, 35 test; `LevelWave` yokken toplama hatasıyla kırmızıydı). Yolda bir
Türkçe büyük harf hatası düzeltildi: pill ve yardım başlıkları `i`'yi `I` yapıyordu
("DINLENIYOR"); `core/i18n.upper()` eklendi. Tam takım: 633 geçti.

⚠️ Dalga yalnız sentetik seviyelerle ve durağan karelerle görüldü; gerçek bir kayıtta, hareket
hâlinde denenmedi.

**Gerçek açılış (duman testi):** uygulama `.venv\Scripts\python main.py` ile başlatıldı, log
okundu, kapatıldı. Hiçbir pencere açılmadı (sürecin ana pencere tutamacı 0), log'da hata yok,
`System ready` 0,4 saniyede, model `cuda/float16` üzerinde 1,4 saniyede yüklendi, ısınma 339 ms.

⚠️ **Denenmedi:** ayar penceresinin gerçek uygulamada açılıp kullanılması, gerçek bir dikte
(canlı bilgi satırları yalnız testte ve ekran görüntüsünde örnek veriyle görüldü), derlenmiş
sürüm, sağdan sola diller, tepsinin gerçekten bulunmadığı bir oturum.

### 2026-10-04 — Tek palet: koyu mavimsi gri, açık tema kalktı

Proje sahibi sepya tonlarını beğenmedi; arka planların koyu mavimsi griye çekilmesini ve açık
temanın kaldırılmasını istedi (ADR-0013).

- `ui/theme.py`: iki Gruvbox paleti (33'er anahtar) yerine tek `PALETTE` (21 renk); vurgu
  rengi sarıdan maviye (`CLR_YELLOW` → `CLR_ACCENT`). Stil dosyasından ölü kurallar (sayı
  kutusu, onay kutusu, düz metin kutusu) ve tema başına simge önbelleği çıktı.
- Kaldırılanlar: `theme` ayarı (`DEFAULTS`), ayar penceresindeki tema seçimi ve
  `theme_changed` sinyali, `main.py`'deki tema bağlantıları (Windows renk tercihini izleyen
  dahil), pill'deki tema dalı ve kullanılmayan `_update_colors`; 11 dilde dört çeviri metni.
- `settings.json`'daki eski `"theme"` satırı silinmez, yalnız okunmaz.

**Testler önce yazıldı.** Kırmızı: `theme` hâlâ ayardı, seçici hâlâ penceredeydi ve ikincil
metin rengi panel zemininde 4,48:1 kontrast veriyordu (sınır 4,5) — renk `#8490a3`'e açıldı.
Yeni korumalar: kodun istediği her renk palette var, kullanılmayan renk yok, arka planlar
koyu ve mavi çekik, metinler okunaklı, `ui/` altında renk sabiti yok. Tam takım (`.venv`):
691 geçti.

**Görsel kontrol:** üç sekme ("her şey yolunda" ve "kayıt çok kısık" senaryoları), pill'in
sekiz karesi ve kullanım kılavuzu penceresi ekran görüntüsüyle incelendi.

⚠️ **Denenmedi:** gerçek uygulamada, gerçek ekranda görünüm; tepsi menüsünün ve açılır
listelerin yeni renkleri ekran görüntüsüyle görülmedi.
