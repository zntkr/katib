# Plan 0014 — Uzun Diktelerde Arka Planda Çözümleme

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **VERİ BEKLİYOR** — Faz 1'in kod kısmı bitti (2026-10-07); ölçüm (`olcum.py --parcali`, plan 0012 Faz 3 ile aynı oturumda) ve proje sahibinin kararı bekleniyor.
**Kullanıcı verisi değişikliği:** YOK (`settings.json` ve veri klasörleri değişmiyor)
**Öncelik:** 🟠 Orta-yüksek — proje sahibinin diktelerinin çoğu 15 sn'yi aşıyor; bugün
bütün çözümleme tuş bırakıldıktan sonra başlıyor ve süre dikte uzunluğuyla büyüyor.
**Tarih:** 2026-10-06
**İlgili belgeler:** `docs/hiz-incelemesi-2026-10-06.md` §9, §11;
`docs/hiz-dogruluk-incelemesi-2026-10-01.md` ("Bilinçli olarak önerilmeyenler" —
canlı transkripsiyon; bu plan o kararı yeni bilgiyle yeniden tartar); plan 0012; plan 0007
**Bağımlılık:** 🛑 SERT: plan 0012 Faz 4 (`decode_options`) önce — parçalı ve bütün
çözümleme aynı ayarları kullanmalı. ⚖️ Yumuşak: plan 0007 Faz 2 (VAD kararı).
**Yeni paket YOK** (Silero VAD faster-whisper'ın içinde).

---

## Neden bu plan

`workers/audio_worker.py::stop_recording` kaydı tek parça `audio_ready` ile gönderir;
`TranscriptionWorker` ancak o zaman başlar. Konuşma sürerken CPU/GPU boştur.
15–30 sn'lik bir dikte tek 30 sn penceredir ama çözümleyici uzun metin üretir;
30 sn+ dikte pencereleri sırayla işler → bırakıştan sonraki bekleme dikte
uzunluğuyla büyür.

İlk tarama "konuşurken canlı transkripsiyon"u gerekçesiyle reddetmişti: yalnız uzun
diktelerde anlamlı, karmaşıklık ekler. 2026-10-06'da proje sahibi diktelerin
çoğunun 15 sn'yi aştığını bildirdi → gerekçenin öncülü değişti. Bu plan **canlı
yazma önermez**: metin yine tuş bırakılınca tek seferde yapıştırılır. Değişen
yalnız çözümlemenin ne zaman yapıldığı.

---

## Devralma notu

```bash
# Faz 0 kararı verildiyse: günlükte seçilen seçenek yazılı
grep -n "Seçilen seçenek" docs/plans/0014-uzun-diktelerde-arka-planda-cozumleme.md
# Faz 1 BİTTİYSE: saf bölme modülü ve ölçüm modu var
ls core/segmenter.py tests/test_segmenter.py
grep -n "\-\-parcali" scripts/olcum.py
# Faz 2 BİTTİYSE (seçenek B): kısmi ses sinyali var
grep -n "partial_audio" workers/audio_worker.py main.py
```

**Ortam**
- Testler: `python -m pytest -q`; referans Windows CI. Whisper ve VAD testlerde sahtedir;
  bölme fonksiyonu VAD parça listeleriyle sınanır (Silero sentetik tonu konuşma saymaz).
- Silero VAD modeli faster-whisper paketinin içindedir (`assets/silero_vad_v6.onnx`); ağ
  gerektirmez, konteynerde gerçekten çalıştırılabilir.
- Gerçek süre ve doğruluk yalnız kullanıcının makinesinde (`olcum/` kayıtları).
- ⚠️ Proje sahibinin makinesinde RTX 4080 var (ADR-0010): `medium` GPU'da 0,2–0,6 sn.
  GPU'da uzun dikte zaten yeterince hızlıysa bu plan **yalnız CPU kullanıcıları** içindir.

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Yapılacak mı | **Ölçüme göre** (Faz 0). Ölçüt: 15 sn+ diktelerde bırakış → yapıştırma p90'ı tipik kurulumda ~1,5 sn'yi aşıyorsa | Karmaşıklık ancak hissedilen bir bekleme için kabul edilir |
| Canlı yazma | **Yok.** Metin bırakışta tek seferde yapıştırılır | Yapıştırılmış metni sonradan düzeltmek imkânsız; UX değişmez |
| Parça sınırı | Silero VAD'ın bulduğu ≥ ~700 ms duraklama, parça en az ~8 sn konuşma | Cümle ortasından kesmemek; çok kısa parça her seferinde 30 sn kodlayıcı bedeli öder |
| Bağlam | Sonraki parçaya kullanıcının `initial_prompt`'u + önceki parçaların son ~200 karakteri | Parça sınırında büyük harf/noktalama ve terim tutarlılığı |
| Bölme mantığı nerede | Saf fonksiyon: `core/segmenter.py::next_cut(audio, start, vad_options) -> int | None` | Worker ve `olcum.py` aynı fonksiyonu kullanır (ölçülen = çalışan); Qt'siz test edilir |
| Oturum durumu nerede | `TranscriptionWorker` (kendi thread'inde): biriken ses, işlenen örnek sayısı, biriken metin | Whisper ve VAD zaten orada; `AudioWorker` yalnız ses taşır |
| Sinyal | `AudioWorker.partial_audio(object)` — yalnız **yeni** bloklar (delta), ~3 sn'de bir; `main.py`'de açıkça bağlanır | Kuyruğa her seferinde bütün kaydı kopyalamamak; CONTEXT.md: tip güvenli sinyal, merkezi kablolama |
| OSD | Kısmi çözümleme `transcription_started/finished` **yaymaz** | Kayıt sürerken OSD "işleniyor"a dönmemeli |
| Kısa dikte | Eşik altı (ör. < 10 sn) kayıt bugünkü yoldan geçer | Kısa diktede davranış birebir aynı kalır |

---

## Faz 0 — Karar (kullanıcı)

- [ ] Plan 0012 Faz 3'ün 15–30 sn ve 30 sn+ kırılımı, CPU ve GPU için.
- [ ] Seçenekler:
  - **0 — Yapma.** Ölçüt aşılmıyorsa (büyük olasılıkla GPU + 0012 ayarlarıyla).
  - **A — Yalnız 30 sn+ için `BatchedInferencePipeline`.** Pencereler toplu (paralel)
    işlenir; 30 sn altı diktede kazanç yok. Küçük değişiklik; ama çıktısı tekli
    yoldan farklı (VAD parçalarını bağımsız çözümler, önceki metne koşullanmaz) →
    WER ayrıca ölçülür.
  - **B — Kayıt sürerken parça parça çözümleme** (bu planın asıl tasarımı, Faz 1–3).
- [ ] 🛑 **0 ya da A seçilirse Faz 1'in kodu silinir:** `core/segmenter.py`,
      `tests/test_segmenter.py`, `scripts/olcum.py`'deki `--parcali` modu ve testleri.
      Yalnız ölçüm için yazıldı; uygulamada kullanılmayan kod olarak kalmaz.
- [ ] Seçilen seçenek ve gerekçesi günlüğe; B seçilirse ADR yazılır (Faz 3).

## Faz 1 — Bölme fonksiyonu ve ölçüm modu (B)

- [x] `core/segmenter.py::next_cut`: `start`'tan sonraki seste, en az ~8 sn konuşmadan
      sonra gelen ilk ≥ ~700 ms duraklamanın ortasını döndürür; yoksa `None`.
      faster-whisper'ın `get_speech_timestamps`'ını kullanır.
- [x] `scripts/olcum.py --parcali`: WAV'ı 3 sn'lik deltalarla besleyerek aynı bölmeyi
      simüle eder; bütün ve parçalı çözümlemenin WER'ini ve "bırakıştan sonra kalan"
      çözümleme süresini yan yana raporlar.
- [x] Testler: sentetik ton + sessizlik dizileri (duraklama yok → `None`; kısa
      konuşmadan sonra duraklama → `None`; uzun konuşmadan sonra duraklama → doğru
      örnek indeksi); `--parcali` raporu (sahte model).
- [ ] Kullanıcı ölçümü: parçalı WER bütüne göre kabul edilebilir mi → günlüğe.

## Faz 2 — Uygulama (B, Faz 1 ölçümü olumluysa)

- [ ] `AudioWorker`: kayıt sürerken ~3 sn'de bir yeni blokları (16 kHz'e çevrilmiş)
      `partial_audio` ile yayar; `stop_recording` bugünkü gibi `audio_ready` ile
      **kalan** sesi ve toplam süreyi bildirir. 🛑 ADR-0007: callback'te yalnız
      biriktirme; yayma `QTimer` ile sahibin thread'inde.
- [ ] `TranscriptionWorker`: kısmi sesi biriktirir; `next_cut` bir sınır verirse o
      parçayı `decode_options` ile çözümler ve metni biriktirir. Kuyruk doluysa kısmi
      iş **atlanır** (son çağrı her şeyi kapsar) — `osd.stt_busy` yayılmaz.
- [ ] Bırakışta: kalan parça çözümlenir, metinler birleşir, uydurma filtresi
      **bütün** dikte süresiyle uygulanır, `text_ready` bir kez yayılır.
- [ ] Kayıt elenirse (çok kısa / sessiz) ya da yeni kayıt başlarsa oturum durumu sıfırlanır.
- [ ] GPU hatasında CPU'ya dönüş kısmi çözümlemede de çalışır (ADR-0010).
- [ ] `tests/test_signal_wiring.py`: yeni sinyal bağlı.
- [ ] Testler: (a) eşik altı kayıt bugünkü yoldan geçer; (b) uzun kayıtta ilk parça
      bırakıştan önce çözümlenir, bırakışta yalnız kalan çözümlenir; (c) metin bir kez
      ve doğru sırayla yapıştırılır; (d) kısmi iş `transcription_started` yaymaz;
      (e) kayıt elenince biriken metin yapıştırılmaz; (f) yeni kayıt eski oturumu taşımaz.

## Faz 3 — Belgeler

- [ ] ADR (sıradaki numara): "Uzun diktelerde arka planda parça çözümleme; canlı yazma yok".
- [ ] CONTEXT.md "Temel İş Akışı" 3–4. adımlar ve `TranscriptionWorker` tanımı.
- [ ] `docs/hiz-dogruluk-incelemesi-2026-10-01.md` notu → bu plana atıfla güncellenir.

---

## Bilinçli olarak YAPILMAYACAKLAR

- **Metni konuşurken imlece yazmak** (akış/canlı yazma).
- **Ayarlara "parçalı çözümleme" anahtarı.** Ölçüm olumluysa herkes için açık;
  değilse hiç yapılmaz.
- **Ayrı bir VAD thread'i veya kütüphanesi.** VAD, Whisper ile aynı thread'de ve
  faster-whisper'ın Silero'su.

## Test stratejisi

Faz 1–2 testleri yukarıda. ⚠️ **Kırmızı kanıtı:** (b) ve (d) bugünkü kodla kırmızı
olmalı. Hız ve WER iddiası yalnız `olcum.py --parcali` ölçümüyle.

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| Parça sınırında kelime kesilir / bağlam kopar | Orta | Yalnız uzun duraklamada kes; önceki metin prompt'a; Faz 1 WER ölçümü kapıdır |
| Kayıt sürerken çözümleme ses callback'ini aç bırakır (GIL) → kayıtta boşluk | Orta | Log'da `Status: input overflow` izlenir; CTranslate2 hesap sırasında GIL'i bırakır, ama Windows'ta doğrulanmalı |
| CPU, parçaları konuşma hızında yetiştiremez | Orta | Kuyruk doluysa kısmi iş atlanır → en kötü durumda bugünkü davranış |
| Toplam hesap artar (her parça ayrı 30 sn kodlayıcı) | Düşük | Parça ≥ ~8 sn; dizüstünde pil etkisi ölçümle bakılır |
| Karmaşıklık: iki yol (kısa/uzun) | Orta | Bölme saf fonksiyonda; eşik altı yol bugünküyle aynı kod |

## Efor

Faz 0: kullanıcı · Faz 1: 3 sa · Faz 2: 4–6 sa · Faz 3: 1 sa (A seçilirse toplam ~2 sa)

---

## Yürütme günlüğü

### 2026-10-06 — Plan açıldı

`docs/hiz-incelemesi-2026-10-06.md` §9'dan; proje sahibinin "diktelerin çoğu 15 sn'yi
aşıyor" bilgisiyle. Kod değişikliği yok.

### 2026-10-07 — Faz 1 (kod) uygulandı

**`core/segmenter.py`** (Qt'siz, saf):
- `next_cut(speeches, length)`: VAD'ın konuşma parçaları arasındaki (ve son parçadan
  sonraki) boşluklardan, en az `MIN_SEGMENT_SECONDS = 8` sn'de başlayan ve en az
  `MIN_PAUSE_SECONDS = 0.7` sn süren **ilkinin ortasını** döndürür.
- `find_cut(audio, threshold)`: Silero'yu `speech_pad_ms=0` ve
  `min_silence_duration_ms=700` ile çalıştırır → parçalar arası boşluklar gerçek
  duraklamalardır. Eşik uygulamanın `vad_parameters["threshold"]`'ı (0.4).
- `context_prompt(user_prompt, text_so_far)`: kullanıcının prompt'u + şimdiye kadarki
  metnin son ~200 karakteri (kelime ortasından başlamaz).

**`scripts/olcum.py --parcali`:** konuşmalı ve ≥ 8,7 sn her kaydı tuş basılıyken ~3 sn'de
bir ses geliyormuş gibi besler; kesim bulunursa o parça "arka planda" çözümlenir, kalan
bırakışta. Rapor: parça sayısı, WER (bütün / parçalı), bırakıştan sonraki Whisper süresi
(bütün / kalan; medyan, p90) ve en yavaş parçanın çözümleme süresi / parça süresi oranı
(< 1: konuşmaya yetişiyor). Çözümleme yardımcısı (`_cozumle`) normal modla ortak.

⚠️ **Plandan sapmalar:**
- Ayrı bir "kısa dikte eşiği" yok: 8 sn'lik asgari parça kuralı onu zaten sağlıyor
  (8,7 sn'den kısa kayıt kesilemez). Bir sabit daha eklemek gereksizdi.
- Testler "sentetik ton" yerine VAD parça listeleriyle yazıldı: Silero sinüs tonunu konuşma
  saymaz; saf fonksiyonu doğrudan sınamak daha kesin. `find_cut`'ın Silero'ya verdiği
  ayarlar sahte modülle sınanıyor (diğer test dosyaları `faster_whisper`'ı `sys.modules`'ta
  `MagicMock` ile değiştirdiği için `patch("faster_whisper.vad...")` sıraya bağlı kırılıyordu).

**Gerçek Silero ile konteynerde doğrulama** (depoya girmedi): `espeak-ng` ile üretilen Türkçe
konuşma (12,4 sn + 1,2 sn duraklama + 10,3 sn + 1,2 sn duraklama + 3,6 sn, hafif gürültülü),
3 sn'lik besleme: 15. sn'de **12,83 sn**'den (duraklama 12,35–13,55), 27. sn'de **24,34 sn**'den
(duraklama 23,88–25,08) kesti; cümle içi kısa duraklamalarda kesmedi; bırakışa 4,4 sn kaldı.
Silero 12–15 sn'lik pencerede ~35–100 ms sürdü. Whisper bu ortamda yok (Hugging Face ağ
politikasıyla kapalı) → WER ve gerçek süre kullanıcı ölçümünde.

**Testler:** `tests/test_segmenter.py` (12), `tests/test_olcum.py` (8 yeni: `TestParcaliCozumle`,
`TestParcaliOlc`, `TestMainParcali`). Tam takım Linux'ta 740 geçti, 7 kırmızı (önceden de
kırmızı olan Windows'a özgü testler). Kırmızı kanıtı: modül ve bayrak yokken test dosyaları
toplanamıyor.

**Kullanıcı için:** plan 0012 Faz 3 ile aynı kayıtlarla, ayrıca:

```powershell
python scripts\olcum.py --parcali --tekrar 3 --dil tr          # CPU/GPU: uygulamanın seçeceği
python scripts\olcum.py --parcali --tekrar 3 --dil tr --cihaz cpu
```

Faz 0 kararı bu raporla verilir: "bırakıştan sonra" süresi belirgin düşüyor, parçalı WER
bütününkünden kötü değil ve "yetişiyor" ise B; değilse 0 ya da A.

### 2026-10-07 — Öz-inceleme

`context_prompt`'taki "kelime ortasından başlama" kırpması kaldırıldı: Whisper yarım kelimeye
takılmaz, kırpma tam kelime sınırına denk gelince fazladan bir kelime siliyordu. Son 200
karakterle sınırlamanın kendisi kalıyor ve gerekçesi koda yazıldı: faster-whisper prompt'un
yalnız son ~223 token'ını tutar (`get_prompt`), kırpılmamış metin en baştaki kullanıcı
prompt'unu dışarı iterdi. Faz 0'a "0 / A seçilirse Faz 1 kodu silinir" maddesi eklendi.

### 2026-10-08 — Seçilen seçenek: B, ve "eller serbest" dikte (proje sahibinin kararı)

Proje sahibi (diktelerinin çoğu 30 sn+; i7-8550U, GPU yok) B'yi seçti ve iki şey daha istedi:
tuşu basılı tutmadan dikte ve konuşma bitince kendiliğinden durma. **"Canlı yazma yok" kararı
kısmen değişti:**

- **Tek tuş, iki kullanım** (`TrayApp`, yeni ayar yok): basılı tut → bırakınca biter (eskisi gibi);
  kısa dokun (< 0,8 sn, `TAP_SECONDS`) → eller serbest: ikinci dokunuşta ya da konuşan susunca biter.
- **Eller serbestte bölümler duraklamada hemen yazılır**; bölüm kesinleşmiştir, sonradan değişmez.
  **Tuş basılıyken yazılmaz**, bırakışta tek seferde yapıştırılır: tuş bastırılmadığı için basılı
  F4'ün yanında gönderilen Ctrl+V, Ctrl+F4 olur.
- **Konuşmanın bittiği** (`core/segmenter.py::speech_is_over`): konuşmadan sonra 3 sn sessizlik ya da
  8 sn hiç konuşma yok. `TranscriptionWorker.speech_ended` → `TrayApp.on_speech_ended`.
- **Plandan sapma (daha sade):** `AudioWorker.partial_audio` delta değil, saniyede bir **o ana kadarki
  bütün kaydı** yayar; worker yalnız "kaç örnek çözümlendi"yi tutar ve boştayken bakar. Bitişte
  `audio_ready` yine bütün kaydı verir, worker kalanını çözümler. Eşik altı kayıt bugünkü yoldan geçer.
- Yeni kayıt `recording_started` → `begin_dictation` ile önceki kaydın bölümlerini siler.

Ölçüm (bu laptop, `small`/int8, sentetik Türkçe ses, 46 sn konuşma, 3 bölüm): bölümler konuşurken
20., 44. ve 50. saniyede yazıldı; mikrofon konuşma bittikten 4 sn sonra kapandı, ardından bekleme
yok. Aynı ses tek parça: bırakıştan sonra 14 sn. WER %5,5 (parçalı) / %4,4 (bütün). Gerçek ses ve
mikrofonla proje sahibi deneyecek. Testler: `TestPieces`, `TestHandsFree`, `TestPartialAudio`,
`TestSpeechIsOver`; tam takım 807 geçti.

Başlangıçta ve bitişte yumuşak bir ton çalar (`core/chime.py`, bellekte üretilir, ses dosyası yok).

**Açık kalan:** ADR; kullanım kılavuzu ve çeviriler hâlâ yalnız "basılı tut" diyor; plan 0012 Faz 4
(`decode_options`) yapılmadı, bütün ve parçalı yol aynı `TRANSCRIBE_OPTIONS`'ı kullanıyor.

### 2026-10-08 (devam) — İlk gerçek deneme (proje sahibi, 104 sn eller serbest dikte)

8 bölüm; 7'si 8,9–20,6 sn'lik ses için 3,9–4,4 sn'de çözüldü ve konuşurken yazıldı; bitişten sonra
bekleme 3,4 sn. **Bir bölüm 57 sn sürdü** ve arkasındaki dört bölüm birikip art arda yazıldı
(ayrıntı ve önlem: plan 0012 günlüğü, aynı tarih). Pill ekranın alt-ortasından **üst-ortasına**
alındı: altta, yazılan yerin (sohbet kutusu, terminal) üstüne geliyordu.

**Bilinen sınır:** bölüm düşünme duraklamasında kesilir; cümle ortasında duraklanırsa iki yarım
ayrı çözümlenir ("…bizim de... Biraz böyle…"). Eşikle giderilemez: konuşan uzun duraklıyor.

### 2026-10-10 — GPU'da eller serbest: cümle duraklamada yazılır (8 sn kuralı yalnız CPU'da kaldı)

Proje sahibi RTX 4080'de large-v3 ile (bırakıştan yazıya 0,35–0,6 sn) şunu bildirdi: eller serbest
diktede metin kendiliğinden gelmiyor, tuşa ikinci kez dokununca yazılıyor. Neden: bölüm en az 8 sn
konuşmadan sonra kesiliyordu; dikteleri 1,3–8,9 sn olduğu için kural hiç devreye girmedi. 8 sn, her
bölümün saniyeler sürdüğü CPU için konmuştu; GPU'da bir bölüm 0,2–0,4 sn.

- **Karar:** eller serbest **ve** model GPU'daysa asgari bölüm 1,5 sn (`MIN_SEGMENT_SECONDS_FAST`);
  duraklama eşiği aynı (0,7 sn). CPU'da ve tuş basılıyken 8 sn kalır: basılı tuşta bölüm yazılmadığı
  için kısa bölüm yalnız cümleyi böler.
- **Reddedilen seçenek, ölçümle:** "cümle kuralı" (saniyede bir yazılmamış sesin tamamını çözümle;
  modelin bitmiş saydığı bölüm iki geçişte aynıysa yaz). Sentetik Türkçe sesle (Windows "Tolga",
  large-v3, GPU) karşılaştırıldı. Duraklamalı 17 sn'lik kayıtta duraklama kuralı her bölümü 0,5–0,7 sn
  sonra, cümle kuralı 2–3,5 sn sonra yazdı; cümle ortasındaki 1,2 sn'lik duraklamada ikisi de aynı
  yerden böldü; tek cümlelik kayıtta cümle kuralı hiç yazmadı. Cümle kuralı yalnız hiç duraklamadan
  konuşulan kayıtta öne geçti (cümleler 5., 10., 13. sn'de; duraklama kuralı 12. sn'de topluca).
  ~100 satır kod ve konuşma boyunca çalışan kart karşılığında bu tek kazanç için alınmadı. Proje sahibi
  duraklamadan uzun konuştuğunu bildirirse yeniden açılır. Canlı metni hapta gösterme fikri de
  reddedildi (proje sahibi: dikkat dağıtır).
- **Doğrulama (gerçek worker, GPU, aynı sentetik kayıtlar):** duraklamalı kayıtta bölümler 3., 7., 10.,
  14., 18. sn'de yazıldı, dikte 21. sn'de kendiliğinden bitti; "Tamam, yarın görüşürüz." 3. sn'de
  yazıldı. Testler: `TestShortPiecesOnTheGpu`.
- **Birlikte düzeltilenler:** (1) Pano: her yapıştırma panoyu ayrı ayrı yedekleyip 150 ms sonra geri
  koyuyordu; art arda iki yapıştırmada kullanıcının panosu kaybolabiliyordu. Yedek artık bir kez
  alınır, son yapıştırmadan sonra bir kez geri konur (`TestPastesInQuickSuccession`). (2) Tek
  çözümlemede birden çok bölüm dönünce aralarına iki boşluk giriyordu (`_decode`).
- ⚠️ **Bekleyen:** proje sahibinin kendi sesiyle denemesi. Bakılacak: kısa bölümlerde uydurma metin,
  düşünme duraklamasında bölünmenin rahatsız edip etmediği. Gerekirse `MIN_SEGMENT_SECONDS_FAST` yükseltilir.
