# Plan 0004 — Log Hattını Tamamlama (ADR-0004'ün kalan yarısı)

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏳ **BAŞLANMADI** — 0/3 faz
**Kullanıcı verisi değişikliği:** YOK (`settings.json` ve veri klasörleri değişmiyor)
**Öncelik:** 🟡 Orta (Faz 1 ses kalitesini etkileyebilir; Faz 2–3 borç)
**Tarih:** 2026-10-01
**İlgili belgeler:** `docs/kod-incelemesi-2026-10-01.md` §5–6,
`docs/adr/0004-centralized-logging-system.md` §6 ("Henüz uygulanmayanlar"),
CONTEXT.md → Anti-Patterns #2 (loglama istisnası), `core/log.py`
**Bağımlılık:** Yok. **Yeni paket YOK** (yalnız stdlib `logging.handlers`).

---

## Neden bu plan

`58e113e` ADR-0004'ü uyguladı: bileşenler `get_logger("<BİLEŞEN>")` ile
logluyor, dosyaya transkript yazılmıyor. İnceleme üç eksik bıraktı:

1. **PortAudio callback'i diske kendisi yazıyor.** Önceden ses thread'i
   sinyal yayıyor, dosyaya ana thread yazıyordu. Şimdi
   `workers/audio_worker.py:199` (taşma uyarısı), `:218`, `:236`, `:245`
   kök logger'daki `RotatingFileHandler`'ı **callback içinde** çalıştırıyor
   (yazma, kilit, gerekirse 5 MB dönüşü). Yükte her taşma uyarısı bir disk
   yazması; callback süresini aşarsa yeni taşma ve ses kaybı.
2. **`setup_logging()` yeniden girişte sonsuz döngü** (konsolsuz mod).
   `main.py:73-74`: ikinci çağrıda `sys.stdout` artık `StreamToLogger`'dır ve
   kök logger'a `StreamHandler(StreamToLogger)` eklenir. Bugün tek çağrı
   olduğu için tetiklenmiyor.
3. **Arayüz bileşenlerinin log satırları diske gitmiyor.**
   `ui/settings_dialog.py` kendi `log_entry` sinyaliyle (satır 47; 413, 442,
   462, 585, 602) ve `ui/dashboard.py` doğrudan `append_log_entry` ile
   (satır 276, 332, 336) logluyor. Destek için önemli olaylar (model
   değiştirme, hassasiyet, ayar sıfırlama, otomatik seçilen mikrofon)
   `katib.log`'da yok; iki log yolu bakım yükü.

---

## Devralma notu

**Nerede kaldık? — depodan doğrula**

```bash
# Faz 1 BİTTİYSE: QueueHandler kurulu → ≥1 satır
grep -n "QueueHandler\|QueueListener" main.py core/log.py
# Faz 2 BİTTİYSE: StreamToLogger'a handler eklenmiyor
grep -n "isinstance(sys.stdout, StreamToLogger)" main.py
# Faz 3 BAŞLAMADIYSA: 5 satır; BİTTİYSE: 0
grep -c "self.log_entry.emit" ui/settings_dialog.py
```

**Ortam**
- Testler: `python -m pytest -q`; referans Windows CI.
- Log testleri: `tests/test_log.py` (dosya ve dashboard yüzeyleri). Worker ve
  arayüz testleri log'u `tests.log_helpers.on_log_entry(callback)` ile gözler;
  `conftest.py` handler'ı her testten sonra söker.

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Diske yazmayı callback'ten çıkarma | Kök logger'a `QueueHandler`; dosya + konsol handler'ları bir `QueueListener` thread'inde | Stdlib'in bu iş için standart çözümü; yeni paket yok |
| Dashboard handler'ı | **Kuyruğa girmez**, `Katib` logger'ında kalır | Zaten yalnız Qt sinyali yayıyor (kuyruklu bağlantı), disk yok |
| Gizlilik | `PrivacyFormatter` dinleyici tarafındaki handler'larda kalır | `QueueHandler.prepare()` mesajı biçimler ama `extra` alanlarını (`transcript`) kopyalar; dosyaya yine yalnız uzunluk gider — **testle kanıtlanmalı** |
| Kapanış | `main.py`'de `app.exec()` sonrası, `logging.shutdown()`'dan önce `listener.stop()` | `os._exit(0)` kuyrukta kalanı atar; `stop()` boşaltır |
| i18n anahtarlı dashboard satırları (`no_mic_found`, `model_missing_guidance`) | **Dashboard'da kalır** | Olay değil, ekran rehberi; dil değişince yeniden çevriliyorlar (`dashboard.py:372-373`) |

---

## Faz 1 — Diske yazma ses thread'inden çıkar

- [ ] `setup_logging()`: dosya ve konsol handler'ları `QueueListener`'a,
      kök logger'a tek `QueueHandler`. Yeniden girişte eski dinleyici durdurulur
      (`_owned_handlers` deseniyle aynı).
- [ ] `main.py` kapanışı: `listener.stop()` → `logging.shutdown()` → `os._exit(0)`.
- [ ] Test: başka bir thread'den loglanan kayıt **dosya handler'ını o thread'de
      çalıştırmaz** (`RotatingFileHandler.emit`'i yamala, çağıran thread'i kaydet).
- [ ] Test: `tests/test_log.py::TestLogFile` testleri kuyrukla da geçer
      (okumadan önce kuyruğu boşalt). Transkript dosyaya **yine** gitmez.

## Faz 2 — `setup_logging()` yeniden girişte güvenli

- [ ] `sys.stdout` bir `StreamToLogger` ise konsol handler'ı eklenmez.
- [ ] Test: `sys.stdout = None` iken iki kez `setup_logging()`, ardından bir
      kayıt → `RecursionError` yok, kayıt dosyada bir kez.

## Faz 3 — Arayüz log'ları da tek yoldan

- [ ] `SettingsDialog`: 5 `log_entry.emit` → `get_logger("APP")`; `log_entry`
      sinyali ve `dashboard.py:536`'daki bağlantısı silinir.
- [ ] `DashboardWindow`: satır 276, 332, 336 → `get_logger("MIC")`.
- [ ] Testler: `tests/test_dashboard.py` (`append_log_entry.assert_called_with`)
      ve `tests/test_ui_interactions.py` / `tests/test_dialogs.py`'deki
      `settings_dialog.log_entry.connect` kullanımları `on_log_entry`'ye çevrilir.
- [ ] ADR-0004 §6 "Henüz uygulanmayanlar" listesinden bu madde düşülür.

⚠️ **Kırmızı kanıtı:** her yeni test, değişiklik geçici geri alındığında
kırmızıya dönmeli.

---

## Bilinçli olarak YAPILMAYACAKLAR

- **Ayarlardan açılan DEBUG modu** (ADR-0004 §2). Kullanıcı talebi yok;
  ihtiyaç doğunca ayrı plan.
- **Ses callback'inde loglamayı kaldırmak.** Taşma ve susturma uyarıları
  destek için değerli; sorun loglama değil, diske yazmanın yeri.
- **Log seviyesini `core/settings.py`'den yönetmek** (ADR-0004 §5). Talep yok.

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| `os._exit` öncesi kuyrukta kalan kayıtlar kaybolur | Orta | `listener.stop()` kapanışta; çökme hook'u da `logging` üzerinden geçtiği için çökmede kuyruk dinleyici thread'i çalışmaya devam eder |
| `QueueHandler.prepare()` istisna metnini mesaja gömer, `exc_info`'yu siler | Düşük | Dosyada traceback yine görünür; çökme dökümü zaten `mask_text` ile maskeli |
| Testlerde dinleyici thread'i sızar | Düşük | `setup_logging()` yeniden girişte eskisini durdurur; `test_log.py` fixture'ı sonunda yeniden kurar |

## Efor

Faz 1: 1 sa · Faz 2: 15 dk · Faz 3: 1 sa → **~2,5 sa**

---

## Yürütme günlüğü

*(henüz yok)*
