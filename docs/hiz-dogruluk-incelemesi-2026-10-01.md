# Hız ve Doğruluk İncelemesi — 2026-10-01

> **Ne bu belge:** Katib'in tek amacına (tuşa basıp konuşulanı mümkün olduğunca
> hızlı ve doğru yazıya dökmek) hizmet etmeyen ya da onu zorlaştıran yapıların
> incelemesi. Hızlı yol baştan sona izlendi: tuş → mikrofon → kayıt →
> sessizlik kontrolleri → Whisper → filtre → yazma.
>
> **Ne değil:** ❌ Plan değil — uygulanacak işler `docs/plans/` altına düşer.
> ❌ Ölçüm değil — 2–4 numaralı bulgular kod okumasıdır, Windows'ta ölçülmedi.

**İnceleme anındaki durum:** `main` = `2fa8ce0`.

---

## 1. ✅ DÜZELTİLDİ (2026-10-01) — Filtre gerçek cümleleri siliyordu *(teyit, çalıştırılarak)*

`core/transcription_filter.py`'deki eski bir kural, normalize edilmiş metnin
**herhangi bir yerinde** "tesekkurler", "ceviri", "sessiz", "muzik", "alkis",
"izlediginiz icin" ya da "altyazi" geçerse cümlenin tamamını atıyordu.
Kullanıcı yalnız "Konuşma algılanmadı" görüyordu. Çalıştırılarak ölçüldü:

```
None <- Toplantı için teşekkürler, yarın görüşürüz.
None <- Bu belgenin çevirisini bana gönder.
None <- Sessiz bir odada çalışmak istiyorum.
None <- Akşam müzik dinledim.
None <- Konuşmanın sonunda alkış koptu.
```

Ayrıca `TranscriptionWorker` filtreye kaydın süresini vermiyordu
(`duration=0.0`), bu yüzden "yalnız 6 saniyeden kısa kayıtlarda uygula" kuralı
her uzunlukta devredeydi.

**Düzeltme:** Alt-dize kuralı kaldırıldı. Kısa bir kayıtta metin **baştan sona
yalnız kalıp ifadelerden** oluşuyorsa atılıyor (`"Altyazı: Müzik"`,
`"Altyazı M.K."`, `"Teşekkürler."`); kalıp kelime cümle içindeyse metin
korunuyor. Worker gerçek süreyi veriyor. Testler:
`tests/test_transcription_filter.py` (12 yeni durum),
`tests/test_transcription_worker_logic.py::TestTranscribeFilterDuration`.

⚠️ **Bilinçli olarak korunan davranış:** kısa bir kayıtta **yalnız**
"Teşekkürler." ya da "Müzik." dikte edilirse hâlâ atılır — Whisper'ın sessizlikte
en sık uydurduğu çıktılar bunlar. Bu ödünleşim §3 ölçülürken yeniden ele alınmalı.

---

## Plana dönüşecek adaylar *(kod okuması, ölçülmedi)*

### 2. 🟠 İlk heceler kesilebilir, başlangıç gecikmeli → [plan 0006](plans/0006-kayit-baslangici-gecikmesi.md)

- Mikrofon her tuş basışında sıfırdan açılıyor (`PortAudioSource.start`); önce
  16 kHz deneniyor, Windows'un ortak ses modu (WASAPI) bunu genelde reddeder ve
  ikinci bir açma denemesi gerekir.
- Tuş 50 ms'de bir yoklanıyor (`HotkeyWorker._run_windows`).
- Sektör çözümü: mikrofonu açık tutup son ~300 ms'yi halka tamponda saklamak
  (tuşa basılmadan önceki ses de kayda girer). Bedeli: Windows'ta "mikrofon
  kullanımda" simgesi Katib açıkken sürekli görünür → **kullanıcı kararı**.

### 3. 🟠 Dört katmanlı sessizlik kontrolü fazla agresif → [plan 0007](plans/0007-sessizlik-katmanlarini-sadelestirme.md)

0,5 sn altı kayıt atılıyor (`MIN_RECORDING_DURATION`); kendi seviye analizimiz
(`core/audio_analysis.is_silent`: konuşma tepesi -55 dB altı ya da 0,3 sn'den az
sesli kısım); Whisper'ın `vad_filter` ve `no_speech_threshold`'u; uydurma
filtresi. Sessiz konuşan kullanıcının ve "Evet." gibi kısa yanıtların kaydı
kaybolabilir. CONTEXT.md'deki "Binary Armor" ilkesiyle ("0.0'dan büyük her
sinyal işlenir") çelişiyor.

### 4. 🟡 Hız için ucuz kazançlar

Model yüklenince bir ısınma transkripsiyonu (→ [plan 0008](plans/0008-model-yuklenince-isinma.md),
kod `main`'de); `beam_size=5` yerine `1` ve
`without_timestamps=True` (doğruluk etkisi ölçülmeli); kısa kayıtlarda hata
yapan otomatik dil algılama yerine dilin bir kez seçilmesi; tuşu yoklama yerine
olayla dinlemek.

### Önce ölçüm altyapısı

2–4'ün hepsi "daha hızlı / daha doğru" iddiası; bunu tartmak için kullanıcının
gerçek kayıtlarından 20–30 kısa WAV + doğru metin ve aşama sürelerini ve kelime
hata oranını ölçen küçük bir betik gerekir.

## Bilinçli olarak önerilmeyenler

Konuşurken canlı transkripsiyon, bulut, LLM ile düzeltme, GPU (CUDA) desteği —
amaca hizmet etmeden karmaşıklık ve paket boyutu ekler.

> ⚠️ **2026-10-03 — GPU maddesi geçersiz.** Proje sahibi hedefi "macOS diktesine
> yakın kalite" olarak netleştirdi ve GPU desteğini onayladı. Karar ve ölçümler:
> [ADR-0010](adr/0010-optional-gpu-acceleration.md); iş:
> [plan 0009](plans/0009-gpu-destegi.md). Diğer üç madde için not geçerliliğini korur.

## Bakılmadı — kapsam sınırı

Gerçek Windows'ta gecikme ve doğruluk ölçümü (cihaz yok); farklı mikrofonlar;
`small` dışındaki modeller.
