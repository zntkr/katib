# Plan 0001 — Bozuk Model Bir Kez Seçilince Model Yükleme Kilitleniyor

> **Bu yaşayan bir belgedir.**
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏳ **BAŞLANMADI**
**Kullanıcı verisi değişikliği:** YOK (`settings.json` ve veri klasörleri değişmiyor)
**Öncelik:** 🔴 Yüksek — kullanıcı uygulamayı yeniden başlatmadan dikteye
dönemiyor ve hata mesajı sebebi söylemiyor ("Model failed to load").
**Tarih:** 2026-10-01
**İlgili belgeler:** `docs/kod-incelemesi-2026-10-01.md` §1

---

## Neden bu plan

`workers/transcription_worker.py:98-99`:

```python
if self._model is not None:
    del self._model
    import gc
    gc.collect()
```

`del self._model` özniteliği **siler**, `None` yapmaz. Ardından gelen
`WhisperModel(...)` hata verirse `self._model` artık tanımsızdır.

### Senaryo (kod okumasıyla, çalıştırılarak denenmedi)

1. Kullanıcı sağlam model A ile çalışıyor.
2. Ayarlardan bozuk ya da yarım inmiş bir klasör seçiyor → `WhisperModel`
   hata verir, `_model` silinmiş kalır, durum "Model Hatası".
3. Kullanıcı model A'ya geri dönüyor → `_load_model_inner` satır 98'de
   `AttributeError: _model` → `except` yakalar → yine "Model Hatası".
4. Uygulama yeniden başlatılana kadar her yükleme düşer.

---

## Devralma notu

**Nerede kaldık? — depodan doğrula, kutulara güvenme**

```bash
# Beklenen (iş BAŞLAMADIYSA): 1 satır
grep -n "del self._model" workers/transcription_worker.py
# Beklenen (iş BİTTİYSE): 0 satır, ve:
grep -n "self._model = None" workers/transcription_worker.py
```

**Ortam**
- Testler: `python -m pytest -q`. Referans ortam **Windows CI**'dır; Linux'ta
  24 test platform nedeniyle kırmızıdır (`docs/kod-incelemesi-2026-10-01.md`).
- `faster_whisper` testlerde `MagicMock` ile değiştirilir
  (`tests/test_transcription_worker_logic.py` üstü), gerçek model gerekmez.

---

## Kararlar ve Uygulama

1. `del self._model` → `self._model = None`. `gc.collect()` kalır: büyük
   modelin belleği yeni model yüklenmeden önce bırakılsın diye vardı.
2. Başka değişiklik yok. 🛑 `_load_model` / `_load_model_inner` ayrımına ve
   `is_loading` mantığına dokunma (plan dışı).

---

## Test stratejisi

`tests/test_transcription_worker_logic.py` içine, mevcut
`_PATCH_MODEL_CLS` desenini kullanarak:

- `test_good_model_loads_again_after_a_failed_load` — 1) yükleme başarılı,
  2) `WhisperModel` hata verir, 3) yükleme yine başarılı → `is_ready is True`
  ve durum `STATE_READY`.

⚠️ **Kırmızı kanıtı:** düzeltmeden önce test kırmızı olmalı (`AttributeError`
yakalanır, `is_ready` False kalır). Kırmızıyı görmeden düzeltmeye geçme.

---

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| `None` atamak eski modeli bellekte tutar | Düşük | `gc.collect()` korunuyor; referans yalnız `self._model`'deydi |

## Efor

Düzeltme: 2 dk · test: 15 dk → **~20 dk**

---

## Yürütme günlüğü

*(henüz yok)*
