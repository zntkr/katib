# Plan 0012 — Çözümleme Ayarları ve Uçtan Uca Gecikme Ölçümü

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **VERİ BEKLİYOR** — Faz 1–2 (2026-10-06) ve Faz 5 (2026-10-07) bitti; Faz 3 kullanıcının ölçümünü bekler.
**Kullanıcı verisi değişikliği:** YOK — Faz 1–4 ve 6. **Faz 5 VAR** (yeni kurulumda ilk
`language` / `initial_prompt` değeri yazılır; mevcut kullanıcılar ve `DEFAULTS` değişmez, taşıma
gerekmez). Proje sahibi açıkça onayladı (2026-10-07; CONTEXT.md → Mimari Kurallar #8).
**Öncelik:** 🟠 Orta-yüksek — dikte süresinin neredeyse tamamı Whisper çağrısında;
buradaki ayarlar kod değişikliği olarak en ucuz, etkisi en büyük kalemler.
**Tarih:** 2026-10-06
**İlgili belgeler:** `docs/hiz-incelemesi-2026-10-06.md` §1–§7, §12;
`docs/hiz-dogruluk-incelemesi-2026-10-01.md` §4; ADR-0010 (ölçümler); plan 0007
(aynı ölçüm betiği ve kayıt seti)
**Bağımlılık:** Faz 4–5 Faz 3'ün ölçümünü bekler. **Yeni paket YOK.**

---

## Neden bu plan

- Kullanıcının hissettiği süre (tuşu bırakma → metnin yapıştırılması) hiçbir
  yerde ölçülmüyor; yalnız model süresi (`dictation_timed`) var.
- `workers/transcription_worker.py::TRANSCRIBE_OPTIONS`: `beam_size=5`, zaman
  damgası token'ları üretiliyor (kullanılmıyor), sıcaklık geri dönüşü varsayılan
  (bir pencere 6 kata kadar yeniden çözümlenebilir).
- Konuşma dili `auto` iken faster-whisper 1.2.1 ilk pencereyi **iki kez** kodluyor
  (kaynak okuması; ayrıntı tarama §2).
- `scripts/olcum.py` ısınma yapmıyor, yalnız CPU'da çalışıyor, çözümleme
  ayarlarını değiştiremiyor → bugünkü hâliyle bu soruları tartamaz.
- `_CPU_THREADS = 0` yorumu yanlış (0 → 4 iş parçacığı).

Proje sahibinin bilgisi (2026-10-06): diktelerin çoğu 15 sn'yi aşıyor. Çözümleyici
süresi metin uzunluğuyla büyüdüğü için §3–§5'in etkisi uzun diktelerde daha
büyüktür → ölçüm seti uzun kayıtları da içermeli.

---

## Devralma notu

**Nerede kaldık? — depodan doğrula**

```bash
# Faz 1 BİTTİYSE: uçtan uca satır loglanıyor
grep -n "release->paste" ui/tray_app.py
# Faz 2 BİTTİYSE: betikte yeni bayraklar
grep -n "\-\-beam\|\-\-cihaz\|\-\-tekrar" scripts/olcum.py
# Faz 4 BAŞLAMADIYSA: sabit sözlük duruyor; BİTTİYSE: decode_options var
grep -n "TRANSCRIBE_OPTIONS = \|def decode_options" workers/transcription_worker.py
# Faz 6 BİTTİYSE: yanlış yorum gitti
grep -n "analyse hardware automatically" workers/transcription_worker.py   # çıktı boş
```

**Ortam**
- Testler: `python -m pytest -q`; referans Windows CI.
- faster-whisper testlerde sahte nesnedir; gerçek süre ve doğruluk yalnız
  kullanıcının makinesinde (`olcum/` kayıtlarıyla) ölçülür.
- 🛑 `olcum/` kullanıcının sesidir: depoya girmez, günlüğe metin değil yalnız sayı
  yazılır (plan 0007, ADR-0004).

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Kuzey yıldızı ölçüt | **Bırakış → yapıştırma** (ms), her dikte için tek log satırı | Kullanıcının hissettiği şey bu; model süresi bunun bir parçası |
| Ölçüt nerede | `TrayApp`: `on_hotkey_released`'ta `perf_counter()`, `on_text_ready`'de fark | Bırakış ve yapıştırma zaten orada; yeni sinyal ya da nesne gerekmez |
| Ayar kaynağı | `TRANSCRIBE_OPTIONS` sabiti yerine `decode_options(device: str) -> dict` | CPU ve GPU'nun bütçesi farklı (GPU beam 5'i kaldırabilir); tek saf fonksiyon, sınıf yok. Betik de aynı fonksiyonu çağırır → ölçülen = çalışan |
| Hangi değerler | **Ölçüme göre** (Faz 3); tahminle değiştirilmez | Doğruluk bedeli kayıtsız tartılamaz |
| Dil varsayılanı | **Kullanıcıya sor** (Faz 5) | Kural #8: varsayılan değişikliği mevcut kullanıcılara da ulaşır |
| Başarı ölçütü | Bırakış → yapıştırma medyanı ve p90'ı düşer; WER bugünkünden kötü değil (ya da kabul edilen bir ödünleşim günlüğe yazılır) | Hız tek başına hedef değil |

---

## Faz 1 — Uçtan uca süre logu

- [x] `TrayApp.on_hotkey_released` bırakış anını tutar; `on_text_ready` yapıştırmadan
      sonra `Dictation done: release->paste N ms (audio X s, model Y ms)` loglar (OK
      seviyesi). Ses ve model süresi için `TrayApp` `dictation_timed`'a bağlandı
      (yeni sinyal yok).
- [x] Kayıt elenirse ya da metin çıkmazsa tutulan an temizlenir; sonraki dikte
      eski anla ölçülmez.
- [x] Test: sahte saatle bırakış + `on_text_ready` → satır var ve süre doğru;
      bırakış olmadan `on_text_ready` → satır yok.

## Faz 2 — Ölçüm betiği bu soruları tartabilsin

- [x] Ölçümden önce ısınma (uygulamadaki `_warm_up` ile aynı iki çağrı).
- [x] `--cihaz cpu|cuda`, `--compute-type`, `--threads`.
- [x] `--beam N`, `--zaman-damgasiz`, `--sicaklik 0` (ya da liste).
- [x] `--tekrar N`: her kayıt N kez; rapor medyan ve p90 verir (ADR-0010'daki
      ölçüm gürültüsü).
- [x] Rapor süreyi ses uzunluğuna göre kırar: < 5 sn, 5–15 sn, 15–30 sn, > 30 sn.
- [x] Testler: bayraklar Whisper çağrısına doğru ayarla gider (sahte model);
      medyan/p90 hesabı; ısınma çağrısı ölçülen süreye girmez.

## Faz 3 — Ölçüm (kullanıcı)

- [ ] Kayıt seti plan 0007'ninkiyle ortak; ek olarak **15–30 sn ve 30 sn+**
      gerçek dikteler (en az 5'er).
- [ ] Önerilen matris (her biri `--tekrar 3`):

```powershell
python scripts\olcum.py                                   # bugünkü ayarlar (referans)
python scripts\olcum.py --dil tr                           # §2: dil sabit
python scripts\olcum.py --dil tr --beam 1                  # §3
python scripts\olcum.py --dil tr --beam 1 --zaman-damgasiz # §4
python scripts\olcum.py --dil tr --beam 1 --zaman-damgasiz --sicaklik 0   # §5
# GPU varsa aynı satırlar --cihaz cuda ile
```

- [ ] Sayılar (metin değil) bu planın günlüğüne.

## Faz 4 — `decode_options(device)`

- [ ] `TRANSCRIBE_OPTIONS` → `decode_options(device)`; değerler Faz 3'e göre.
      `_decode`, `_warm_up` ve `scripts/olcum.py` aynı fonksiyonu çağırır.
- [ ] 🛑 VAD ayarları (`vad_filter`, `vad_parameters`) bu planın konusu değil;
      plan 0007 karar verene kadar olduğu gibi kalır.
- [ ] Testler: CPU ve GPU için dönen sözlük ölçümde seçilen değerleri taşır;
      worker `_decode` yüklü modelin cihazına göre çağırır; GPU'dan CPU'ya
      dönüşte CPU ayarları kullanılır.

## Faz 5 — Konuşma dili varsayılanı (kullanıcı kararı)

✅ **Karar (proje sahibi, 2026-10-07):** ölçüm beklenmeden **B'nin bir türevi** — yalnız
**yeni kurulumda** (açılışta `settings.json` yoksa) konuşma dili bilgisayarın diline ayarlanır;
listede yoksa **otomatik algılama** (İngilizce değil: Felemenkçe konuşan birini İngilizceye
zorlamak metni bozar, algılama Felemenkçe yazar). Dilin hazır prompt'u da birlikte yazılır,
kullanıcı ayar penceresinden seçmiş gibi. **Mevcut kullanıcılar etkilenmez:** `DEFAULTS`
değişmedi (`auto`), taşıma kodu gerekmedi. Gerekçe: dil sabitlemenin hız kazancı kaynak
okumasıyla kesin (tarama §2, ikinci kodlayıcı geçişi), kısa kayıtta yanlış dil riski bilinen
bir sorun; ölçüm yalnız kazancın büyüklüğünü söyler.

Seçenekler:
- **A — `auto` kalır.** Faz 3 dil sabitlemenin kazancını küçük gösterirse.
- **B — Varsayılan: uygulama dili** (yoksa sistem dili; `SPEECH_LANGUAGES`'ta yoksa
  `auto`). ⚠️ Yalnız varsayılandan farklı değerler kaydedildiği için `auto`'da
  bırakan mevcut kullanıcılar da yeni varsayılana geçer → ya bu bilinçli kabul
  edilir ya da taşıma kodu mevcut `settings.json`'a açıkça `"language": "auto"` yazar.
- **C — İlk açılışta bir kez sor.** Over-UI kuralıyla (CONTEXT.md yasak #8) tartılmalı.

## Faz 6 — Küçük kalemler

- [x] `_CPU_THREADS` yorumu düzeltilir.
- [ ] Faz 3'te `--threads` ölçümü kazanç gösterirse değer fiziksel çekirdek sayısından
      türetilir (ölçüm yoksa 0 kalır).
- [x] Çift kopya: `AudioWorker._audio_callback` kaynağın zaten kopyaladığı bloğu
      yeniden kopyalamaz (tarama §12). Test: kaynaktan gelen dizi kayda bir kez girer.

---

## Bilinçli olarak YAPILMAYACAKLAR

- **Ayarlara "beam / sıcaklık" seçeneği.** Kullanıcı ayar kurcalamamalı; varsayılan
  doğru olmalı (0007 ile aynı ilke).
- **Ölçümsüz değer değişikliği.**
- **`BatchedInferencePipeline`.** 30 sn altı dikte tek penceredir, kazancı yok;
  30 sn+ için plan 0014'te seçenek.

## Test stratejisi

Her fazın testi yukarıda. ⚠️ **Kırmızı kanıtı:** Faz 1 ve Faz 4 testleri bugünkü
kodla kırmızı olmalı. Hız ve doğruluk iddiası yalnız Faz 3 ölçümüyle yapılır.

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| `beam_size=1` uzun diktede WER'i bozar | Orta | Faz 3 uzun kayıtları ayrıca raporlar; GPU'da beam 5 kalabilir |
| `without_timestamps=True` 30 sn+ seste pencere ilerletmesini bozar | Orta | 30 sn+ kayıtlar ayrı kırılımda; bozulursa yalnız kısa seste uygulanır |
| `temperature=0` tekrar döngüsünü kurtaramaz | Düşük–orta | `condition_on_previous_text=False` zaten açık; liste kısaltılır, tamamen kaldırılmaz |
| Dil varsayılanı mevcut kullanıcıyı sessizce değiştirir | Yüksek | Faz 5 açık onay + taşıma kodu |

## Efor

Faz 1: 45 dk · Faz 2: 2 sa · Faz 3: kullanıcı · Faz 4: 1 sa · Faz 5: 1–2 sa · Faz 6: 30 dk

---

## Yürütme günlüğü

### 2026-10-06 — Plan açıldı

`docs/hiz-incelemesi-2026-10-06.md`'nin §1–§7 ve §12 bulgularından. Kod değişikliği yok.

### 2026-10-06 — Faz 1–2 uygulandı

**Faz 1:** `TrayApp` bırakış anını (`perf_counter`) tutuyor ve `on_text_ready` metni
yapıştırdıktan sonra tek satır yazıyor:
`Dictation done: release->paste 1840 ms (audio 18.2 s, model 1620 ms)` (`Katib.APP`, OK).
Ses ve model süresi `dictation_timed`'dan geliyor; `main.py`'de `TrayApp`'e de bağlandı.
An; yeni basışta, `transcription_finished`'ta (konuşma yok / hata) ve satır yazılınca
temizleniyor; reddedilen basış (model yükleniyor) zaman başlatmıyor. ⚠️ `inject_text()`
`processEvents()` çağırdığı için kuyruktaki `transcription_finished` yapıştırma sırasında
gelip anı silebiliyordu (ilk yazımda yakalandı) → an yapıştırmadan **önce** alınıyor;
testi var. ⚠️ Plandan sapma:
log satırı ASCII `->` kullanıyor (PowerShell'de `Select-String` kalıbı kolay olsun diye).

**Faz 2:** `scripts/olcum.py`: `--cihaz auto|cpu|cuda` (varsayılan `auto`, uygulama gibi
`core.gpu`'ya sorar), `--compute-type`, `--threads`, `--beam`, `--zaman-damgasiz`,
`--sicaklik 0` / `0,0.4`, `--tekrar N` (süre medyandır). Rapor her kaydın uzunluğunu
gösteriyor ve Whisper süresini medyan/p90 olarak `< 5 / 5–15 / 15–30 / > 30 sn`
kırılımıyla veriyor; başta kullanılan cihaz ve çözümleme ayarları yazılıyor.
Ölçümden önce ısınma: uygulamanın `_warm_up` gövdesi `workers/transcription_worker.py::warm_up(model, language, options)`
olarak dışarı alındı; worker ve betik aynı fonksiyonu, betik ölçülen ayarlarla çağırıyor.

⚠️ **Plan dışı küçük düzeltme:** `--dil auto` elle verilirse betik Whisper'a
`language="auto"` geçiriyordu (faster-whisper bunu `'auto' is not a valid language code` ile
reddeder). Artık `auto` → `None`. ~~Varsayılan ayarlı kullanıcıda betik hiç çalışmazdı~~ —
**yanlış iddia, 2026-10-07'de düzeltildi:** `SettingsManager.get("language")` `auto` için
zaten `None` döndürüyor; varsayılan yol hiç bozuk değildi. Yanlış iddiayı "doğrulayan" test,
gerçeğinden farklı cevap veren sahte bir ayar nesnesi kullanıyordu.

**Testler:** `tests/test_tray_app.py::TestDictationLatency` (7),
`tests/test_olcum.py` (15 yeni: `TestCozumleme`, `TestTekrar`, `TestSureOzeti`,
`TestModelAc`, `TestMain`). Tam takım Linux'ta: 718 geçti, 7 kırmızı — değişiklikten
önceki 7 Windows'a özgü testin aynısı. Kırmızı kanıtı: `tray_app.py` geri alınınca 4 gecikme
testi kırmızı (2'si "satır yazılmaz" testleri, ikisinde de doğal olarak yeşil); an
yapıştırmadan sonra alınınca `processEvents` testi kırmızı; `olcum.py`
geri alınınca test dosyası toplanamıyor. Konteynerde Hugging Face erişimi yok (ağ
politikası) → gerçek modelle duman testi yapılamadı; betiğin geçirdiği bütün ayar adları
`WhisperModel.transcribe` imzasında var (faster-whisper 1.2.1, `inspect.signature` ile doğrulandı).

**Kullanıcı için (Faz 3):** kayıt seti `olcum\` klasörüne (0007 ile ortak; 15–30 sn ve
30 sn+ dikteler dahil). Her satırı `--tekrar 3` ile çalıştırıp raporları (metinsiz) buraya:

```powershell
python scripts\olcum.py --tekrar 3                                          # bugünkü ayarlar
python scripts\olcum.py --tekrar 3 --dil tr                                 # §2 dil sabit
python scripts\olcum.py --tekrar 3 --dil tr --beam 1                        # §3
python scripts\olcum.py --tekrar 3 --dil tr --beam 1 --zaman-damgasiz       # §4
python scripts\olcum.py --tekrar 3 --dil tr --beam 1 --zaman-damgasiz --sicaklik 0   # §5
# GPU varsa aynı satırlar --cihaz cuda ile; CPU için ayrıca --cihaz cpu --threads 8
```

Uygulamanın kendisinde: birkaç gerçek dikteden sonra
`Select-String -Path "$env:LOCALAPPDATA\Katib\Logs\katib.log" -Pattern "release->paste"`.

### 2026-10-07 — Faz 6'nın ölçüm istemeyen kısmı

`_CPU_THREADS` yorumu düzeltildi (0 → CTranslate2'nin varsayılanı, 4 iş parçacığı).
`AudioWorker._audio_callback` artık bloğu yeniden kopyalamıyor; `AudioSource.start`
belgesine "alıcı kendi dizisini alır, kaynak onu yeniden kullanmaz" sözleşmesi yazıldı.
Testler: `tests/test_audio_worker.py::TestChunkOwnership` (kopya geri gelince kırmızı),
`tests/test_portaudio_source.py::TestChunkCopy` (sözleşmenin kaynak tarafı: PortAudio
tamponu sonradan değişse de alıcının dizisi değişmez). İş parçacığı sayısı Faz 3 ölçümünü bekliyor.

### 2026-10-07 — Öz-inceleme düzeltmeleri

Proje sahibinin "aşırı mühendislik / tekerleği yeniden icat etme var mı" sorusu üzerine
kendi değişikliklerim gözden geçirildi:
- **`olcum.py --cihaz` uygulamanın `compute_device` ayarına uymuyordu.** `model_ac`, worker'ın
  cihaz seçiminin sade bir kopyası; kopyada ayar atlanmıştı → `compute_device=cpu` olan
  kullanıcıda betik GPU'yu ölçerdi. Varsayılan artık ayardan okunuyor; bayrak yine ezer.
  Seçim kodunu worker ile ortaklaştırmak (durumlu, CPU'ya dönüşlü metot) ~10 satırlık
  tekrardan pahalı olduğu için yapılmadı.
- **Faz 2 günlüğündeki "`auto` dili betiği bozuyordu" iddiası yanlıştı** (yukarıda düzeltildi).
  `tests/test_olcum.py::TestMain` artık gerçek `SettingsManager`'ı (bellekte) kullanıyor.
- Testler: `test_the_device_follows_the_apps_compute_device_setting` (eski varsayılanla
  kırmızı), `test_cihaz_overrides_the_setting`, `test_dil_auto_on_the_command_line_means_detection`.

### 2026-10-07 — Faz 5 uygulandı

- `core/settings.py::first_run_speech_settings(system_code)` → `{"language", "initial_prompt"}`:
  bilgisayarın dili `SPEECH_LANGUAGES`'ta varsa o dil ve hazır prompt'u, yoksa `auto` ve boş prompt.
- `SettingsManager.first_run`: yüklemede `settings.json` yoksa `True` (bellekte kullanımda hep `False`).
  Yalnız tüm ayarları varsayılan olan eski bir kullanıcının da dosyası vardır (açılışta
  `app_language` yazılıyor) → yanlışlıkla "yeni kurulum" sayılmaz.
- `main.py`: `migrate_legacy_data()` ve `SettingsManager()` sonrasında, `app_language` yazılmadan
  önce tek çağrı: `settings_manager.set_many(first_run_speech_settings(system_language_code()))`.
  Bilgisayarın dili arayüz dilinin kullandığı fonksiyonla okunuyor (`core/i18n.system_language_code`).
- Hazır prompt tablosu `ui/settings_window.py::_DEFAULT_PROMPTS` → `core/settings.py::DEFAULT_PROMPTS`
  (veri; çekirdek de kullanıyor). ⚠️ Plandan sapma / bulgu: ayar penceresi ayarları widget'lara
  kurucuda değil `show()`'da işliyor; ilk denemede yalnız dili yazmak, model önceden kurulmuş
  (pencere açılmayan) kurulumda dili prompt'suz bırakırdı. Bu yüzden prompt da birlikte yazılıyor.

**Testler:** `tests/test_config.py::TestFirstRunSpeechLanguage` (8: listede olan / olmayan /
bilinmeyen dil, her listelenen dilin hazır prompt'u var, `first_run` dosya yok / var / bellekte,
yazılan değer kalıcı), `tests/test_settings_window.py::TestSpeechLanguageAndPrompt::test_the_first_run_language_and_prompt_are_what_the_window_shows`.
Tam takım Linux'ta 752 geçti, 7 kırmızı (önceden de kırmızı olan Windows'a özgü testler).

⚠️ **Not (düzeltilmedi, kapsam dışı):** `core/i18n.system_language_code()` `locale.getdefaultlocale()`
kullanıyor; Python 3.11'den beri kullanımdan kalkmış, 3.15'te kaldırılması planlanıyor. Proje 3.14'e
sabit (`.python-version`); 3.15'e geçerken bu fonksiyon değişmeli (arayüz dili de aynı fonksiyonu kullanıyor).

### 2026-10-08 — CPU ölçümü (i7-8550U, GPU yok) ve `beam_size` 5 → 2

Sentetik Türkçe ses (Windows TTS; proje sahibinin sesi değil), `small`/int8, dil `tr`, 5 kayıt
(2,5 / 6 / 13 / 28 / 44 sn), her biri 2 koşu. Whisper süresi (ms) ve ortalama WER:

| Ayar | 2,5 sn | 6 sn | 13 sn | 28 sn | 44 sn | WER |
|---|---|---|---|---|---|---|
| beam 5 (eski) | 3735 | 4517 | 7098 | 13396 | 23625 | %5,5 |
| beam 2 | 2992 | 3397 | 4536 | 7215 | 12705 | %6,7 |
| beam 1 | 2928 | 3302 | 4385 | 6579 | 13386 | %8,5 |
| beam 5, zaman damgasız | 3794 | 4339 | 6005 | 10555 | 19763 | %4,8 |

İş parçacığı (13 sn'lik kayıt): 2 → 7274, 3 → 7087, 4 → 6600, 6 → 7558, 8 → 8317 ms; varsayılan (4)
en iyisi. Zaman damgasız + beam 1 ve sıcaklık 0 tutarlı kazanç vermedi (ölçüm gürültüsü içinde).
**Karar (proje sahibi, "milisaniye kovalamayalım"):** yalnız `beam_size` 2 yapıldı, tek satır;
`decode_options(device)` yazılmadı, yani GPU da beam 2 kullanıyor.

### 2026-10-08 (devam) — `beam_size` yeniden 5; sıcaklık listesi `[0.0, 0.4]`

Proje sahibi ilk gerçek denemeden sonra: "doğruluk düşüşü kabul edilemez". Plan 0014 çözümlemeyi
konuşmanın arkasına aldığı için beam 5'in bedeli artık bitişte değil konuşurken ödeniyor →
**`beam_size` 5'e geri alındı.**

Aynı denemede 9,1 sn'lik bir bölüm **57 sn'de** çözüldü (diğer bölümler ~4 sn); o sırada kullanıcı
duraksayıp mırıldanıyordu. En olası neden sıcaklık geri dönüşü (tarama §5: 6 deneme × ~9 sn);
**doğrulanamadı** — sentetik seste gürültü (SNR 20/5/0 dB) geri dönüşü tetiklemedi. Yine de liste
`[0.0, 0.4]` yapıldı (en kötü durum 6 deneme yerine 2) ve ikinci deneme olursa günlüğe
`Low-confidence audio: decoded a second time` yazılıyor: sıçrama tekrarlanırsa neden görülecek.
