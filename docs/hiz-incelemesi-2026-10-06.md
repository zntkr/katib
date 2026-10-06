# Hız İncelemesi — 2026-10-06

> **Ne bu belge:** Diktenin **tuşu bırakmaktan metnin yazılmasına** kadar geçen
> süresini kısaltacak yerlerin ikinci taraması. İlk tarama
> (`docs/hiz-dogruluk-incelemesi-2026-10-01.md`) tuş, mikrofon ve sessizlik
> katmanlarına bakmıştı; bu belge ağırlıkla **Whisper çağrısının içine** bakar.
> Her bulgu nasıl doğrulandığıyla yazıldı.
>
> **Ne değil:** ❌ Plan değil — işler `docs/plans/0012`–`0014`'e ve 0006/0007'ye
> düştü. ❌ Ölçüm değil — süre iddiaları kaynak okumasıdır; gerçek süreler
> yalnız kullanıcının Windows makinesinde ölçülebilir (konteynerde ses aygıtı
> ve model yok).

**İnceleme anındaki durum:** `main` = `dd76a22`. faster-whisper `1.2.1`
(`requirements.txt`'teki sürüm); kaynağı paket arşivinden açılıp okundu.

**Proje sahibinden yeni bilgi (2026-10-06):** Diktelerin çoğu **15 saniyeyi
aşıyor**. İlk taramanın "canlı transkripsiyon yalnız uzun diktelerde anlamlı,
önerilmez" gerekçesi bu bilgiyle yeniden tartılmalı (§9).

---

## Özet

| # | Bulgu | Etki | Doğrulama | Plan |
|---|---|---|---|---|
| 1 | Süre bütçesinin neredeyse tamamı Whisper; uçtan uca süre ölçülmüyor | — | Kod okuması + ADR-0010 ölçümleri | [0012](plans/0012-cozumleme-ayarlari-ve-gecikme-olcumu.md) Faz 1 |
| 2 | Konuşma dili `auto` iken kodlayıcı ilk 30 sn'de **iki kez** çalışıyor | 🟠 | faster-whisper kaynak okuması | 0012 Faz 5 |
| 3 | `beam_size=5` | 🟠 | Kod okuması | 0012 Faz 4 |
| 4 | Zaman damgası token'ları üretiliyor, kullanılmıyor | 🟡 | Kaynak okuması | 0012 Faz 4 |
| 5 | Sıcaklık geri dönüşü bir pencereyi 6 kata kadar yeniden çözümleyebilir | 🟠 (en kötü durum) | Kaynak okuması | 0012 Faz 4 |
| 6 | `_CPU_THREADS = 0` yorumu yanlış: 0 → 4 iş parçacığı | 🟢 | Kaynak okuması | 0012 Faz 6 |
| 7 | `olcum.py` ısınma yapmıyor, yalnız CPU'da, çözümleme ayarı değiştiremiyor | 🟠 (ölçümü bozar) | Kod okuması | 0012 Faz 2 |
| 8 | `large-v3-turbo` listede yok | 🟠 | Kaynak okuması | [0013](plans/0013-large-v3-turbo-modeli.md) |
| 9 | Uzun diktelerde bütün iş tuş bırakıldıktan sonra başlıyor | 🟠 (15 sn+ diktelerde) | Kod okuması | [0014](plans/0014-uzun-diktelerde-arka-planda-cozumleme.md) |
| 10 | Ön-kayıt için "ilk basışta uyan, N dk açık kal" seçeneği | — | Tasarım | [0006](plans/0006-kayit-baslangici-gecikmesi.md) Faz 4, seçenek C |
| 11 | Silero VAD mi, kendi seviye analizimiz mi? | — | Kaynak + kod okuması | [0007](plans/0007-sessizlik-katmanlarini-sadelestirme.md) |
| 12 | Her ses bloğu iki kez kopyalanıyor | 🟢 | Kod okuması | 0012 Faz 6 |

---

## 1. Süre nereye gidiyor

| Aşama | Yer | Durum |
|---|---|---|
| Tuş | `workers/hotkey_worker.py` | Olayla dinleniyor (0006 Faz 3) |
| Mikrofonun açılması | `core/portaudio_source.py::start` | Tek denemede (0006 Faz 2) |
| Bırakışta birleştirme / örnekleme / seviye | `workers/audio_worker.py::stop_recording` | UI thread'de, ms düzeyinde tahmin (0005 ölçecek) |
| **Whisper** | `workers/transcription_worker.py::_decode` | **Bütçenin neredeyse tamamı** |
| Yazma | `core/text_injector.py` | Pano yolu hızlı; eski pano 150 ms sonra arka planda geri yüklenir |

ADR-0010: `small` CPU int8 1065 / 2105 ms, `medium` CPU 3458 / 6424 ms,
`medium` GPU float16 179 / 601 ms. Whisper kodlayıcısı her pencereyi **30 sn'ye
doldurur** (`pad_or_trim`); kısa bir kayıt da kodlayıcıda 30 sn'lik bedel öder.
Çözümleyici (decoder) süresi ise üretilen token sayısıyla, yani konuşmanın
uzunluğuyla büyür. 15 sn+ diktelerde çözümleyicinin payı artar → §3–§5'in
etkisi uzun diktelerde daha büyüktür.

**Eksik:** Kullanıcının hissettiği süre (bırakış → yapıştırma) hiçbir yerde
ölçülmüyor. `dictation_timed` yalnız model süresini veriyor, `@measure_time`
yalnız `_transcribe`'ı.

## 2. Dil `auto` iken kodlayıcı iki kez çalışıyor *(kaynak okuması)*

`core/settings.py::DEFAULTS["language"] = "auto"` → `_target_language()` `None`
döndürür. faster-whisper 1.2.1 `transcribe.py`:

- `WhisperModel.transcribe` `language is None` iken `self.detect_language(features=...)`
  çağırır; o fonksiyon ilk 30 sn'yi **kendisi kodlar** (`encoder_output = self.encode(...)`)
  ve yalnız dili döndürür.
- Ardından `generate_segments(..., encoder_output)`'a giden değişken hâlâ `None`'dır;
  `if seek > 0 or encoder_output is None: encoder_output = self.encode(segment)` →
  aynı pencere **ikinci kez** kodlanır.

Kodlayıcı, kısa kayıtta sürenin büyük kısmıdır (ör. `large-v3` ve turbo 32
katmanlı kodlayıcı taşır). Ayrıca kısa kayıtta dil algılama yanlış dil
seçebilir (ilk tarama §4). Dili sabitlemek hem hız hem doğruluk kazancıdır.
⚠️ Varsayılanı değiştirmek CONTEXT.md kural #8'e göre **kullanıcı verisi
değişikliğidir** (yalnız varsayılandan farklı değerler kaydedildiği için yeni
varsayılan mevcut kullanıcılara da ulaşır) → açık onay ister.

## 3. `beam_size=5` *(kod okuması)*

`workers/transcription_worker.py::TRANSCRIBE_OPTIONS`. Beam search her adımda 5
aday taşır; açgözlü çözümleme (`beam_size=1`) çözümleyiciyi belirgin hızlandırır,
doğruluk etkisi dikte gibi temiz, tek konuşmacılı seste genelde küçüktür —
**ölçülmeden iddia edilemez.** GPU'da beam'in maliyeti düşük olduğundan cihaza
göre farklı değer mantıklı olabilir.

## 4. Kullanılmayan zaman damgası token'ları *(kaynak okuması)*

`WhisperModel.transcribe` varsayılanı `without_timestamps=False` (aynı
kütüphanenin toplu `BatchedInferencePipeline`'ında varsayılan `True`). Katib
segment zamanlarını kullanmıyor; yalnız `seg.text` birleştiriliyor.
`without_timestamps=True` her segmentte üretilen zaman token'larını kaldırır.
⚠️ Zaman damgaları uzun seste pencere ilerletmesine de katılır (`seek`); 30 sn+
kayıtlarda doğruluk ayrıca ölçülmeli.

## 5. Sıcaklık geri dönüşü *(kaynak okuması)*

Varsayılan `temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]`,
`compression_ratio_threshold=2.4`, `log_prob_threshold=-1.0`.
`generate_with_fallback` bir pencerenin sonucu bu eşikleri tutturamazsa aynı
pencereyi bir sonraki sıcaklıkla **yeniden çözümler** — en kötü durumda 6 kez.
Gürültülü ya da kısık kayıtlarda ara sıra görülen "bu sefer neden çok uzun
sürdü" sıçramasının olası kaynağı. `temperature=0.0` ya da kısa bir liste
(`[0.0, 0.4]`) üst sınırı keser; bedeli: tekrar döngüsüne giren bir çıktının
kurtarılamaması. Ölçülmeli.

## 6. `_CPU_THREADS = 0` *(kaynak okuması)*

`workers/transcription_worker.py:6` yorumu "CTranslate2 donanımı otomatik
analiz etsin" diyor. faster-whisper `WhisperModel.__init__` belgesi:
"`cpu_threads`: Number of threads to use when running on CPU (**4 by default**)".
Yani 0 → 4 iş parçacığı. ADR-0010'da 16 iş parçacığı kazanç vermedi (ölçüm
gürültülüydü). Fiziksel performans çekirdeği sayısıyla (ör. 8) bir kez
ölçülmeli; en azından yorum düzeltilmeli.

## 7. Ölçüm betiğinin eksikleri *(kod okuması)*

`scripts/olcum.py`:
- **Isınma yok:** modeli yükleyip doğrudan ilk kaydı ölçüyor; ilk kaydın
  süresi CTranslate2 çekirdek kurulumunu ve VAD modelinin yüklenmesini içerir
  (plan 0008'in uygulamadan kaldırdığı bedel). Ortalama yukarı kayar.
- **Yalnız CPU:** `device="cpu"` sabit; proje sahibinin makinesinde GPU var.
- **Çözümleme ayarları değiştirilemiyor:** §2–§5'i tartmak için bayrak yok.
- **Tek koşu, ortalama:** ADR-0010 aynı ayarın başka ölçümde 2 kat yavaş
  çıktığını not ediyor → tekrar + medyan gerekir.
- **Süre kırılımı yok:** 15 sn+ diktelerin ayrı raporlanması gerekir (§9).

## 8. `large-v3-turbo` *(kaynak okuması)*

faster-whisper 1.2.1 `utils.py::_MODELS` `"large-v3-turbo"` ve `"turbo"` adlarını
`mobiuslabsgmbh/faster-whisper-large-v3-turbo` deposuna eşliyor (Systran bu
modeli yayımlamıyor). Turbo, `large-v3`'ün kodlayıcısını (32 katman) ve
4 katmanlı bir çözümleyiciyi taşır; çok dillidir. Çözümleyici payı büyük olan
uzun diktelerde `large-v3`'e göre çok daha hızlı olması beklenir; kodlayıcı aynı
olduğundan CPU'da kısa kayıtta kazanç sınırlıdır. GPU'lu kullanıcı için
"macOS diktesine yakın kalite" hedefinin doğal adayı. `distil-*` modelleri
ağırlıkla İngilizcedir; Türkçe için uygun değil.

## 9. Uzun diktelerde bütün iş bırakıştan sonra *(kod okuması)*

`AudioWorker` kaydı bellekte biriktirir, `stop_recording` bitince
`audio_ready` ile tek parça gönderir; Whisper ancak o zaman başlar. 15–30 sn'lik
bir dikte tek pencere ama çözümleyici uzun metin üretir; 30 sn+ dikte pencereleri
**sırayla** işler. Konuşma sürerken CPU/GPU boştur.

İlk tarama "konuşurken canlı transkripsiyon"u önermemişti (karmaşıklık, amaca
hizmet etmiyor). Önerilen şey **canlı yazma değildir**: metin yine tuş
bırakılınca tek seferde yapıştırılır; yalnız tamamlanmış cümleler (VAD'ın
bulduğu duraklamalara kadar) konuşma sürerken arka planda çözümlenir, bırakışta
yalnız son parça kalır. Bedel: her parça ayrı bir 30 sn'lik kodlayıcı geçişi
öder (toplam hesap artar ama konuşmanın arkasına saklanır); parça sınırında
bağlam kaybı → önceki parçanın metni `initial_prompt`'a verilir. Ölçümle
kapılanır: GPU'da 20 sn'lik dikte zaten ~1 sn altındaysa yapılmaz.

## 10. Ön-kayıt: "ilk basışta uyan, N dakika açık kal"

Plan 0006 Faz 4'ün iki seçeneği vardı: A (yapma), B (Katib açıkken mikrofon hep
açık). Proje sahibinin önerisi üçüncü bir yol: mikrofon ilk basışta açılır, kayıt
bitince kapanmaz, **son kullanımdan N dakika sonra** kapanır; açık kaldığı sürede
son ~300 ms halka tamponda tutulur ve sonraki basışta kaydın başına eklenir.
Değerlendirme ve tasarım: plan 0006 → Faz 4, seçenek C.

Bilinmesi gereken bedeller (kod ve platform bilgisi, ölçülmedi):
- **Bluetooth kulaklık:** Windows mikrofon açıkken kulaklığı "Hands-Free"
  profiline geçirir; müzik/ses N dakika boyunca telefon kalitesine düşer.
- **Uyku/uyanma ve cihaz değişikliği:** açık stream ölür → bugün
  `_on_stream_finished` bunu "mikrofon koptu" hatası olarak OSD'ye taşır;
  boştaki (kayıt yapmayan) stream için bu hata sessizce yutulmalı.
- `refresh_devices()` açık stream varken PortAudio'yu yeniden başlatmıyor
  (`core/portaudio_source.py`) → cihaz listesi yenilenmeden önce boştaki stream
  kapatılmalı.

## 11. Silero VAD mi, kendi seviye analizimiz mi? *(kaynak + kod okuması)*

| | `core/audio_analysis.is_silent` | Whisper `vad_filter` |
|---|---|---|
| Ne | Enerji (RMS) eşiği: tepe < -55 dB, < 0,3 sn sesli, düz ve kısık | Silero VAD v6 (ONNX sinir ağı, `faster_whisper/assets/silero_vad_v6.onnx`) |
| Ne bilir | Yalnız "ne kadar yüksek" | "Bu ses konuşma mı" — fan, klavye, müzik konuşmadan ayrılır |
| Karar | Kaydın **tamamına** evet/hayır | Konuşma bölümlerini bulur, aradaki sessizliği atar |
| Kırılgan olduğu yer | Kısık mikrofon / fısıltı (sabit dB eşiği); yüksek sesli gürültü geçer | Yumuşak başlayan kelime (dolgu `speech_pad_ms=400` ile azaltılmış) |

Silero daha kararlıdır: konuşmayı enerjiye değil içeriğe göre tanır ve
sabit bir dB eşiğine bağlı değildir. Kendi analizimiz uzun diktelerde zaten
neredeyse hiç devreye girmez (15 sn'lik konuşmada 0,3 sn sesli bölüm ve -55 dB
tepe her zaman aşılır); yalnız kısa basışlarda ve kısık mikrofonda karar verir —
yani tam da yanlış negatif riskinin olduğu yerde. Uzun diktelerde Silero'nun
değeri artar: düşünme duraklamaları Whisper'ın en çok uydurduğu yerdir ve 30 sn
sınırını aşan sesi kısaltır. Plan 0007'nin hedef yapısı (seviye analizini yalnız
"tam sıfır" ve "yanlışlıkla dokunuş"a indirmek, sessizlik kararını Silero'ya
bırakmak) bu karşılaştırmayla tutarlı; karar yine Faz 1b ölçümüyle verilir.

## 12. Çift kopya *(kod okuması)*

`core/portaudio_source.py::_sd_audio_callback` `indata.copy()` ile,
`workers/audio_worker.py::_audio_callback` yine `indata.copy()` ile kopyalıyor.
Bloğa ~4 KB, maliyeti mikrosaniye düzeyinde; temizlik.

---

## Bilinçli olarak önerilmeyenler

- **Akış (streaming) ile canlı yazma** — metni konuşurken imlece yazmak:
  geri alınamayan, sonradan düzeltilen metin; ilk taramanın gerekçesi geçerli.
  §9 bunun yerine bırakışta tek yapıştırmayı korur.
- **asyncio, olay yolu, servis katmanları** — CONTEXT.md yasaklıyor; darboğaz
  CTranslate2'nin içinde, Python mimarisinde değil.
- **Başka bir VAD kütüphanesi** — Silero zaten faster-whisper'ın içinde (0007).

## Bakılmadı — kapsam sınırı

Gerçek Windows'ta süre ve doğruluk ölçümü (cihaz yok); `BatchedInferencePipeline`'ın
30 sn+ diktelerde ölçümü (0014'te seçenek olarak duruyor); `hotwords` ve
`initial_prompt` uzunluğunun süreye etkisi.
