# Plan 0005 — Ses İşlerinin UI Thread'de Çalışması: Ölç, Sonra Karar Ver

> **Bu yaşayan bir belgedir.**
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **VERİ BEKLİYOR** — kullanıcının Windows ölçümü gerekiyor
(2026-10-01). Ölçüm gelmeden kod yazılmaz.
**Kullanıcı verisi değişikliği:** YOK (`settings.json` ve veri klasörleri değişmiyor)
**Öncelik:** ⏸️ Ölçüme bağlı
**Tarih:** 2026-10-01
**İlgili belgeler:** CONTEXT.md → Mimari Kurallar #2 ("Bilinen istisna"),
ADR-0007, `workers/audio_worker.py`, `workers/base_worker.py::measure_time`

---

## Neden bu plan

Worker'lar `QThread` alt sınıfıdır ve nesneleri ana thread'de yaşar. Bu
yüzden `AudioWorker`'ın slot'ları (`start_recording`, `stop_recording`,
`refresh_devices`) **ana (UI) thread'de** çalışır; `run()` yalnız bekler.
`refresh_devices()` PortAudio'yu kapatıp yeniden başlatır (`sd._terminate()`
/ `sd._initialize()`) ve mikrofon takılıp çıkarıldığında arayüzü
dondurabilir. Bu CONTEXT.md kural 2'ye aykırıdır.

Doğru çözüm büyük: `AudioWorker`'ı gerçek bir worker thread'e taşımak ve
**bütün PortAudio çağrılarını tek thread'de toplamak**. Etkisi bilinmeden
bu riski almak aşırı mühendislik olur. `1b5f475` iki işlemin süresini
loglamaya başladı; karar o sayılarla verilecek.

---

## Devralma notu

**Ölçüm nasıl alınır (kullanıcı, Windows'ta):**

1. Katib'i başlat, birkaç kez mikrofon tak/çıkar, birkaç kez dikte yap.
2. Log dosyasında UI thread sürelerini listele:

   ```powershell
   Select-String -Path "$env:LOCALAPPDATA\Katib\Logs\katib.log" -Pattern "UI thread"
   ```

   Satırlar şöyle görünür:
   `Katib.MIC | [Device refresh (UI thread)] completed: 6.9 ms`
   `Katib.MIC | [Stop recording (UI thread)] completed: 12.3 ms`

3. En yüksek değerleri bu planın "Yürütme günlüğü"ne yaz.

**Karar kuralı (önceden kararlaştırıldı):**

| En yüksek süre | Karar |
|---|---|
| < 100 ms | Durum belgelenir (yeni ADR), plan **kapanır**. `measure_time` satırları kalabilir |
| ≥ 100 ms | `AudioWorker` gerçek worker thread'e taşınır — **ayrı plan** açılır |

⚠️ Konteynerde (Linux, cihazsız) ölçülen `6.9 ms` yalnız boş cihaz listesi
içindir; karar için **kullanmayın**.

---

## ≥ 100 ms çıkarsa yeni planın sınırları (şimdiden not)

- 🛑 Bütün PortAudio çağrıları (`start`, `stop`, `refresh_devices`,
  `set_device`) **tek bir thread'de** yapılmalı; PortAudio çağrıları
  thread'ler arası güvenli değil.
- 🛑 ADR-0007: callback içinden PortAudio yeniden başlatılmaz.
- `main.py` merkezi kablolaması korunur (ADR-0003); `TrayApp` worker'a
  doğrudan çağrı yerine sinyal yayar.
- `tests/test_audio_worker.py` ve `tests/test_audio_resilience.py`
  davranış testleri yeni yapıda da geçmeli.

## Bilinçli olarak YAPILMAYACAKLAR

- **Ölçümsüz taşıma.** Neden bu plan → yukarıda.

---

## Yürütme günlüğü

*(ölçüm bekleniyor)*
