# Plan 0002 — Kayıt Bitince Mikrofon Stream'i Kapatılmayabilir

> **Bu yaşayan bir belgedir.**
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ✅ **KAPANDI** 2026-10-01
**Kullanıcı verisi değişikliği:** YOK (`settings.json` ve veri klasörleri değişmiyor)
**Öncelik:** 🟠 Orta-yüksek — açık kalan stream cihazı meşgul tutabilir ve
yerel kaynak sızdırır; hata sessiz yutulduğu için log'da da görünmez.
**Tarih:** 2026-10-01
**İlgili belgeler:** `docs/kod-incelemesi-2026-10-01.md` §2, ADR-0007
(PortAudio callback kuralları)

---

## Neden bu plan

`core/portaudio_source.py:135-145`:

```python
def stop(self) -> None:
    self._close_dead_stream()
    if self._stream is not None:
        self._intentional_close = True
        try:
            self._stream.stop()      # ← finished callback burada çalışabilir
            self._stream.close()     # ← self._stream artık None olabilir
        except Exception:
            pass                     # ← AttributeError sessizce yutulur
        finally:
            self._stream = None
```

`stream.stop()` sırasında PortAudio `_sd_finished_callback`'i (satır 175)
çağırır; o da `self._stream = None` yapar. Callback `stop()` dönmeden
çalışırsa `close()` hiç çağrılmaz.

⚠️ Callback'in `stop()` içinde mi sonra mı çalıştığı ses sürücüsüne (host
API) bağlı; tetiklenme sıklığı **ölçülemedi** (konteynerde cihaz yok).

---

## Devralma notu

**Nerede kaldık? — depodan doğrula**

```bash
# Beklenen (iş BAŞLAMADIYSA): stop() içinde self._stream.close() satırı var
sed -n '/def stop/,/def native_sample_rate/p' core/portaudio_source.py | grep -n "self._stream.close()"
# Beklenen (iş BİTTİYSE): stop() yerel değişken kullanıyor
sed -n '/def stop/,/def native_sample_rate/p' core/portaudio_source.py | grep -n "stream = self._stream"
```

**Ortam**
- Testler: `python -m pytest -q`; referans Windows CI.
- `sounddevice` testlerde `conftest.py`'de global `MagicMock`'tur; yeni test
  dosyası `tests/test_portaudio_source.py` bu deseni zaten kullanıyor.

---

## Kararlar ve Uygulama

1. `stop()` stream'i önce yerel değişkene alır, `self._stream`'i hemen
   `None` yapar, sonra `stop()` ve `close()`'u yerel değişken üzerinden
   çağırır. Callback'in `self._stream = None` yapması artık zararsız.
2. `except Exception: pass` kalır — kapanıştaki sürücü hataları kullanıcıya
   gösterilecek bir şey değil. ⚖️ Ama yutulan hata `_log.warning` ile
   loglanmalı (ADR-0004: sessiz hata yasak). `_log` modülde
   `get_logger("MIC")` olarak tanımlı değil → `PortAudioSource` için
   `core/portaudio_source.py`'ye `get_logger("MIC")` eklenir.
3. 🛑 ADR-0007 kuralı korunur: callback içinde `close()` çağrılmaz.

---

## Test stratejisi

`tests/test_portaudio_source.py`:

- `test_stop_closes_stream_even_if_finished_callback_runs_inside_stop` —
  `stream.stop` mock'unun `side_effect`'i `source._sd_finished_callback()`
  çağırır (en kötü sürücü davranışı) → `stream.close` bir kez çağrılmış olmalı.
- `test_stop_logs_close_errors` — `stream.close` hata verirse uyarı loglanır
  (`tests.log_helpers.on_log_entry`).

⚠️ **Kırmızı kanıtı:** ilk test bugünkü kodla kırmızı olmalı.

---

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| `_sd_finished_callback` `_intentional_close`'u okumadan önce `self._stream` değişir | Düşük | `_intentional_close = True` `stop()`'tan önce kurulur, sıra korunur |

## Efor

Düzeltme: 10 dk · 2 test: 20 dk → **~30 dk**

---

## Yürütme günlüğü

### 2026-10-01 — uygulandı, kapandı

`PortAudioSource.stop()` stream'i yerel değişkene alıyor ve `self._stream`'i
`stop()`'tan önce `None` yapıyor; `stop()`/`close()` yerel referans üzerinden.
Kapanış hatası artık yutulmuyor: `Katib.MIC` uyarısı olarak loglanıyor
(`core/portaudio_source.py`'ye `get_logger("MIC")` eklendi). Plandan sapma yok.

**Testler** (`tests/test_portaudio_source.py::TestStop`):
`test_stop_closes_stream_even_if_finished_callback_runs_inside_stop` (en kötü
sürücü davranışı: callback `stream.stop()` içinde çalışır) ve
`test_stop_logs_close_errors`. Kırmızı kanıtı: ikisi de düzeltmeden önce
kırmızıydı. Ses testleri: 23 geçti.

⚠️ Gerçek sürücüde callback'in `stop()` içinde çalışıp çalışmadığı hâlâ
ölçülmedi; düzeltme her iki sırada da doğru.
