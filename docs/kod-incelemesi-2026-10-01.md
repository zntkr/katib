# Kod İncelemesi — 2026-10-01

> **Ne bu belge:** 30 Eylül – 1 Ekim 2026'daki mimari düzeltmelerin
> (`9bd6ec8..e2ac44d`, 18 commit, 71 dosya) baştan sona gözden geçirilmesi.
> Her bulgu **nasıl doğrulandığıyla** birlikte yazıldı.
>
> **Ne değil:** ❌ Sistematik bir güvenlik denetimi değil. ❌ Plan değil —
> uygulanacak işler `docs/plans/` altına düştü, bu belge onların kanıt
> kaynağıdır. Kapsam sınırı en altta ("Bakılmadı") açıkça yazılı.

**İnceleme anındaki durum:** `main` = `e2ac44d`. Windows CI (GitHub Actions,
`windows-latest`) yeşil. Linux konteynerinde 24 test kırmızı; hepsi platforma
özgü ve bilinen (sistem tepsisi yok, X ekranı yok, `ctypes.windll` yok).

**Yöntem:** Otomatik inceleme (`/code-review`) 10 aday bulgu üretti. Her
aday kod okunarak ya da küçük bir deneyle **tek tek doğrulandı**: 6'sı
gerçek, 1'i asılsız, 3'ü bilinçli olarak plana dönüştürülmedi.

---

## Özet

| # | Bulgu | Şiddet | Doğrulama | Plan |
|---|---|---|---|---|
| 1 | Bozuk model bir kez seçilince model yükleme kalıcı kilitleniyor | 🔴 | Kod okuması | [0001](plans/0001-bozuk-model-sonrasi-yukleme-kilidi.md) |
| 2 | Kayıt bitince mikrofon stream'i kapatılmayabilir | 🟠 | Kod okuması | [0002](plans/0002-kayit-sonunda-stream-kapanmiyor.md) |
| 3 | Kayıt, devam eden indirmenin durum bildirimini siliyor | 🟡 | Kod okuması | [0003](plans/0003-durum-satirinda-kalan-iki-kacak.md) |
| 4 | Dil değişince tepsi ipucu "Hazır"a dönüyor | 🟡 | Kod okuması | [0003](plans/0003-durum-satirinda-kalan-iki-kacak.md) |
| 5 | PortAudio callback'i log satırını diske kendisi yazıyor | 🟡 | Kod okuması | [0004](plans/0004-log-hattini-tamamlama.md) |
| 6 | `setup_logging()` iki kez çağrılırsa konsolsuz modda sonsuz döngü | 🟢 | Kod okuması | [0004](plans/0004-log-hattini-tamamlama.md) |
| — | Arayüz bileşenlerinin log satırları diske gitmiyor (ADR-0004'ün yarısı) | 🟡 | Bilinen, ADR-0004 §6'da yazılı | [0004](plans/0004-log-hattini-tamamlama.md) |
| — | `AudioWorker` slot'ları UI thread'de çalışıyor | ⏸️ | Bilinen, CONTEXT.md kural 2 notu | [0005](plans/0005-ses-islerinin-ui-thread-olcumu.md) |

---

## 1. 🔴 Bozuk model bir kez seçilince model yükleme kilitleniyor *(eskiden beri var)*

`workers/transcription_worker.py:98-99`:

```python
if self._model is not None:
    del self._model
```

`del` değişkeni `None` yapmaz, **özniteliğin kendisini siler**. Ardından
`WhisperModel(...)` hata verirse (bozuk/yarım klasör) `self._model` artık
yoktur. Bir sonraki yeniden yüklemede `if self._model is not None`
`AttributeError` fırlatır; `try` bunu yakalar ve "Model failed to load"
der. Sağlam modele dönülse bile **her yükleme düşer**, uygulama yeniden
başlatılana kadar.

**Doğrulama:** Kod okuması. Çalıştırılarak denenmedi (gerçek model yok).

## 2. 🟠 Kayıt bitince mikrofon stream'i kapatılmayabilir *(eskiden beri var)*

`core/portaudio_source.py:140-141`:

```python
self._stream.stop()
self._stream.close()
```

`stream.stop()` sırasında PortAudio "stream bitti" callback'ini
(`_sd_finished_callback`, satır 175) çalıştırır ve o `self._stream = None`
yapar. Callback `stop()` dönmeden çalışırsa `self._stream.close()`
`AttributeError` verir, `except Exception: pass` yutar, stream açık kalır.
Callback'in `stop()` içinde mi sonra mı çalıştığı sürücüye bağlı.

**Doğrulama:** Kod okuması. Gerçek ses cihazı olmadığı için tetiklenme
sıklığı ölçülemedi.

## 3. 🟡 Kayıt, devam eden indirmenin durum bildirimini siliyor *(2026-10-01 değişikliği)*

`ui/tray_app.py:175` — `set_recording(True)` `_download_notice`'i koşulsuz
siler. Model indirilirken dikte yapılırsa, kayıt bitince durum satırı
indirme sürerken "Hazır" gösterir.

## 4. 🟡 Dil değişince tepsi ipucu "Hazır"a dönüyor

`ui/tray_app.py:78` — `apply_language()` tepsiyi `_build_tray()` ile
yeniden kurar; o da satır 86'da ipucunu sabit `STATE_READY` yazar ve simgeyi
boşta simgesine çevirir. `_resolve_status()` çağrılmaz. Mikrofon yokken dil
değiştirilirse tepsi "Hazır" der.

## 5. 🟡 PortAudio callback'i log satırını diske kendisi yazıyor *(2026-10-01 değişikliği)*

ADR-0004 uygulanmadan önce ses thread'i `log_entry` sinyalini yayıyor, dosyaya
**ana thread** yazıyordu. Şimdi `workers/audio_worker.py:199` (taşma
uyarısı), `:218` (susturulmuş mikrofon), `:236`, `:245` doğrudan `logging`
çağırıyor; kök logger'daki `RotatingFileHandler` yazmayı ve gerekirse 5 MB
dönüşünü **PortAudio callback'inin içinde** yapıyor. Sistem yükteyken her
taşma uyarısı bir dosya yazması demek; callback süresini aşarsa yeni
taşmalar ve ses kaybı doğar.

## 6. 🟢 `setup_logging()` iki kez çağrılırsa konsolsuz modda sonsuz döngü

`main.py:73-74` — ilk çağrı konsolsuz modda `sys.stdout`'u `StreamToLogger`
yapar. İkinci çağrıda `sys.stdout is not None` doğru olur ve kök logger'a
`StreamHandler(StreamToLogger)` eklenir: her kayıt kendini yeniden loglar.
Bugün `setup_logging()` yalnız bir kez çağrıldığı için **tetiklenmiyor**;
ama fonksiyon tekrar çağrılabilir diye yazıldı (`_owned_handlers`).

---

## Bakıldı, temiz

- **"`muted_detected` lambda'sı PortAudio thread'inde çalışıp OSD widget'ına
  dokunuyor" — ASILSIZ.** Deneyle ölçüldü: ana thread'de yaşayan bir
  QObject'in sinyali başka bir Python thread'inden yayıldığında, bağlı lambda
  da bound slot da **ana thread'de** çalıştı (çıktı:
  `[('lambda', 'MainThread'), ('bound', 'MainThread')]`, PySide6 güncel sürüm).
  ⚠️ Bu PySide6'nın davranışıdır; sürüm sabitlenmediği için (`requirements.txt`
  pinsiz) gelecekte değişirse yeniden ölçülmeli.

## Bilinçli olarak plana dönüştürülmeyenler

- **Eski ayarların taşınması varsayılanları da kopyalıyor.** Eski sürümler
  `settings.json`'a tüm varsayılanları yazıyordu; `migrate_legacy_data()`
  bunları olduğu gibi taşıyor. Türkçe varsayılanlar (`"language": "tr"`)
  **hiçbir yayın sürümünde bulunmadı** (son sürüm v1.0.0, Mayıs 2026; Türkçe
  varsayılan 28 Ağustos'ta geldi, 1 Ekim'de geri alındı). Etki yalnız
  geliştirme sürümü kullananlarda.
- **Algılanan arayüz dili kalıcı kaydediliyor.** İlk açılışta algılanan
  sistem dili `app_language`'a yazılıyor; Windows dili sonradan değişirse
  takip edilmiyor. Eski kod da böyleydi; ayarlar penceresi kayıtlı değeri
  gösterdiği için korundu (`main.py`, `resolve_app_language`).

## Bakılmadı — kapsam sınırı

- **Gerçek Windows çalışma zamanı.** Konteynerde masaüstü, sistem tepsisi ve
  mikrofon yok; mikrofon çekme, susturma, oturum açılışında başlatma elle
  denenmedi.
- **Kurulum paketi.** `Katib.iss` depoda yok; kaldırıcının hangi klasörleri
  sildiği okunamadı.
- **`feature/whisper-cpp-migration` dalı.** İncelemenin kapsamı yalnız `main`.
- **Görsel arayüz.** Ekran görüntüsü alınmadı.

## Yeniden üret

```bash
git diff 9bd6ec8..e2ac44d --stat     # incelenen aralık
python -m pytest -q                   # Windows'ta tam paket yeşil olmalı
```
