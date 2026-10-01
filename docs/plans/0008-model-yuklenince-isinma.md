# Plan 0008 — Model Yüklenince Isınma Transkripsiyonu

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **VERİ BEKLİYOR** — kod `main`'de (2026-10-01); kazancı kullanıcının
Windows log'uyla doğrulanacak (Faz 2).
**Kullanıcı verisi değişikliği:** YOK (`settings.json` ve veri klasörleri değişmiyor)
**Öncelik:** 🟡 Orta — günün ilk diktesi, sonrakilerden belirgin yavaş olabilir;
kullanıcının uygulama hakkındaki ilk izlenimi o dikte.
**Tarih:** 2026-10-01
**İlgili belgeler:** `docs/hiz-dogruluk-incelemesi-2026-10-01.md` §4 (ilk madde),
`workers/transcription_worker.py`

---

## Neden bu plan

faster-whisper'ın ilk `transcribe()` çağrısı tek seferlik bedeller öder:
CTranslate2 çekirdeklerini ve bellek havuzunu kurar, faster-whisper VAD
modelini (Silero, ONNX) ilk `vad_filter=True` çağrısında yükler
(`faster_whisper/vad.py::get_vad_model`, `functools.lru_cache`). Bugün bu bedeli
kullanıcının **ilk diktesi** ödüyor.

Kaynak okumasıyla doğrulandı (faster-whisper 1.2.1, `transcribe.py` ~885–1010):
sessiz bir kayıtta `vad_filter=True` sesi tamamen atar, `generate_segments`
döngüsü hiç dönmez — **kod çözücü çalışmaz**. Dil sabitse kodlayıcı da çalışmaz.
Yani tek bir "sessizliği uygulamanın ayarlarıyla çevir" çağrısı ısıtmaz.
⚠️ Kazancın büyüklüğü **ölçülmedi** (cihaz yok).

---

## Devralma notu

```bash
# Faz 1 BİTTİYSE: ısınma yerinde
grep -n "_warm_up\|Warm-up done" workers/transcription_worker.py
python -m pytest -q tests/test_transcription_worker_logic.py -k WarmUp
```

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Ne çevrilir | 1 sn sessizlik, iki çağrı: `vad_filter=False` (kodlayıcı + kod çözücü) ve uygulamanın `TRANSCRIBE_OPTIONS`'ı (VAD modeli) | Yukarıdaki kaynak okuması; tek çağrı kod çözücüyü atlar |
| Dil | Kullanıcının seçtiği dil (`auto` → algılama yolu da ısınır) | Gerçek dikteyle aynı yol |
| Ne zaman | Model "hazır" bildirildikten **sonra**, worker thread'inde | Açılış uzamaz. Bu arada gelen dikte kuyrukta bekler ve en fazla soğuk çağrının bedeli kadar bekler — bugünden kötü değil |
| Hata | Yalnız uyarı log'u; model hazır kalır | Isınma bir iyileştirme; başarısızlığı dikteyi engellememeli |
| Yeniden yükleme | Her başarılı yüklemeden sonra (model değişince yeni model soğuktur) | `_load_model` tek giriş noktası |

## Faz 1 — Isınma

- [x] `TranscriptionWorker._warm_up()`; `_load_model` başarılıysa çağırır.
- [x] `Warm-up done (N ms)` / `Warm-up failed: …` log'u (`Katib.STT`).
- [x] Dil seçimi `_target_language()`'a alındı; `_transcribe` ile ortak.

## Faz 2 — Windows'ta doğrulama (kullanıcı)

- [ ] Uygulamayı açın, `Warm-up done (N ms)` satırını bekleyin, ardından üç
      kısa dikte yapın. Log'daki `Whisper Transcription` sürelerinden ilki
      diğer ikisine yakınsa ısınma işe yarıyor. N ve üç süre buraya yazılır.

---

## Bilinçli olarak YAPILMAYACAKLAR

- **Hazır bildirimini ısınma bitene kadar ertelemek** — açılışı uzatır, kazancı yok.
- **faster-whisper iç fonksiyonlarını (ör. `get_vad_model`) doğrudan çağırmak** —
  iç API'ye bağımlılık; genel `transcribe()` aynı işi görüyor.
- **`beam_size`, `without_timestamps`, dil seçimi** (§4'ün diğer maddeleri) —
  doğruluk etkisi plan 0007'nin ölçüm betiğiyle tartılmadan değişmez.

## Test stratejisi

`tests/test_transcription_worker_logic.py::TestWarmUp` (6): iki çağrı (biri VAD'sız,
biri uygulamanın ayarlarıyla) ve ikisinin de tüketildiği; seçili dil; ısınma
sırasında model zaten hazır; süre log'u; hata yalnız uyarı; yükleme başarısızsa
ısınma yok. **Kırmızı kanıtı:** `_warm_up` yokken ilk beş kırmızıydı (altıncı,
"yükleme başarısızsa ısınma yok", doğası gereği bugün de yeşil).

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| Uygulama kapanırken ısınma sürüyorsa kapanış ~1–3 sn gecikir | Düşük | Kapanış zaten `os._exit` ile biter |
| Kazanç küçük çıkar | Düşük | Faz 2 ölçer; küçükse kod ~15 satır, zararsız |

## Efor

~30 dk

---

## Yürütme günlüğü

### 2026-10-01 — Faz 1

`_warm_up()` eklendi. Plandan sapma yok. Tam test takımı: Linux'ta yalnız
önceden de kırmızı olan 12 Windows'a özgü test kırmızı (değişiklikten önce ve
sonra aynı liste); referans Windows CI.
