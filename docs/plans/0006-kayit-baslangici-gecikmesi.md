# Plan 0006 — Kayıt Başlangıcı: Gecikme ve Kesilen İlk Hece

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** 🔄 **DEVAM EDİYOR** — 3/4 faz (2026-10-01). Faz 4 Faz 1 ölçümünü ve kullanıcı kararını bekliyor.
**Kullanıcı verisi değişikliği:** YOK (`settings.json` ve veri klasörleri değişmiyor;
çalışan örnekleme hızı yalnız bellekte tutulur)
**Öncelik:** 🟠 Orta-yüksek — ilk hecenin kaybolması doğrudan doğruluk kaybıdır;
programın tek amacı "tuşa bas, söyle, yazılsın".
**Tarih:** 2026-10-01
**İlgili belgeler:** `docs/hiz-dogruluk-incelemesi-2026-10-01.md` §2, ADR-0007
(PortAudio callback kuralları), plan 0005 (ses işlerinin UI thread ölçümü)
**Bağımlılık:** Yok. **Yeni paket YOK.**

---

## Neden bu plan

Tuşa basıldığı an ile ilk ses parçasının kayda girdiği an arasında üç gecikme
kaynağı var (kod okuması, Windows'ta **ölçülmedi**):

1. **Tuş yoklaması.** `workers/hotkey_worker.py::_run_windows` tuşu 50 ms'de bir
   `keyboard.is_pressed()` ile okuyor → basışta ve bırakışta 0–50 ms gecikme;
   50 ms'den kısa bir dokunuş hiç görülmeyebilir.
2. **Mikrofon her basışta sıfırdan açılıyor.** `core/portaudio_source.py::start`
   her seferinde `sd.InputStream` kuruyor.
3. **İlk açma denemesi büyük olasılıkla başarısız.** `start()` önce 16 kHz
   istiyor. Windows'un ortak ses modu (WASAPI) cihazın kendi hızı (genelde
   44,1/48 kHz) dışındaki hızları dönüştürme bayrağı olmadan reddeder; kod
   hatayı yakalayıp cihazın kendi hızıyla **ikinci kez** açıyor. Her basışta.

Kullanıcı tuşa basıp hemen konuşursa bu süre boyunca söylenen kayda girmez.

⚖️ **Sektör deseni:** dikte araçları ya mikrofonu açık tutup son birkaç yüz
milisaniyeyi bir halka tamponda saklar (tuşa basılmadan önceki ses de kayda
girer), ya da en azından açma süresini tek ve hızlı bir işleme indirir. İlki
gizlilik/sistem simgesi bedeli taşır (Faz 4).

---

## Devralma notu

**Nerede kaldık? — depodan doğrula**

```bash
# Faz 1 BİTTİYSE: basış → ilk ses parçası süresi loglanıyor
grep -n "First audio" workers/audio_worker.py
# Faz 2 BİTTİYSE: WASAPI dönüştürme bayrağı ya da hatırlanan hız kullanılıyor
grep -n "auto_convert\|_working" core/portaudio_source.py
# Faz 3 BAŞLAMADIYSA: 1 satır (yoklama döngüsü); BİTTİYSE: 0
grep -c "currently_down = keyboard.is_pressed" workers/hotkey_worker.py
```

**Ortam**
- Testler: `python -m pytest -q`; referans Windows CI. `sounddevice` ve
  `keyboard` testlerde `MagicMock`'tur (`tests/conftest.py`,
  `tests/test_hotkey_worker.py`, `tests/test_portaudio_source.py`).
- Doğrulandı (2026-10-01, konteyner): `sounddevice` 0.5.6'da
  `sd.WasapiSettings(exclusive=False, auto_convert=False, explicit_sample_format=False)`;
  `keyboard` 0.13.5'te `on_press_key(key, callback, suppress=False)` ve
  `on_release_key`. ⚠️ `requirements.txt` sürüm sabitlemiyor; kullanıcının
  makinesindeki sürüm farklı olabilir → Faz 2'de geri dönüş yolu korunur.
- 🛑 **Gerçek gecikme yalnız Windows'ta ölçülebilir** (konteynerde cihaz yok).

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Önce ne | **Faz 1: ölç** | "Kaç ms kaybediyoruz" bilinmeden Faz 4'e (bedelli) karar verilemez |
| Tek açılış | Önce `WasapiSettings(auto_convert=True)` ile 16 kHz; olmazsa cihazın kendi hızı ve **o hız bellekte hatırlanır** | Sonraki basışlar tek denemede açılır; yeniden örnekleme de (doğrusal, filtresiz) çoğu cihazda devreden çıkar |
| Hatırlanan hız nerede | Yalnız `PortAudioSource` örneğinde, cihaz değişince sıfırlanır | `settings.json`'a yazmak kullanıcı verisi değişikliği olurdu (CONTEXT.md kural #8); gereği yok |
| Tuş | `keyboard.on_press_key` / `on_release_key` olayları | Yoklama gecikmesi ve kaçan kısa dokunuş biter; Linux yolu (`pynput`) zaten olay tabanlı |
| Ön-kayıt tamponu | **Kullanıcı kararı** (Faz 4) | Bedeli: Katib açıkken Windows'ta "mikrofon kullanımda" simgesi sürekli görünür |

---

## Faz 1 — Ölç: basıştan ilk ses parçasına

- [x] `AudioWorker.start_recording()` başlangıç zamanını tutar; ilk
      `_audio_callback` çağrısında `First audio after N ms` (`Katib.MIC`, OK)
      loglanır. 16 kHz açma reddedilip cihaz hızına düşüldüyse bu da loglanır.
- [x] Test: sahte kaynakla `start_recording()` + bir callback → log satırı var.
- [ ] Kullanıcıdan Windows ölçümü (plan 0005 ile aynı yöntem):
      `Select-String ... -Pattern "First audio"`. Sonuç "Yürütme günlüğü"ne.

## Faz 2 — Mikrofon tek denemede açılır

- [x] Windows'ta ilk deneme `extra_settings=sd.WasapiSettings(auto_convert=True)`
      ile 16 kHz. `WasapiSettings` yoksa/hata verirse mevcut geri dönüş
      (cihazın kendi hızı) çalışır ve **başarılı hız `_working`'te
      hatırlanır**; sonraki `start()` doğrudan o hızla açar.
- [x] `set_device()` farklı cihaza geçince `_working` sıfırlanır.
- [x] 🛑 ADR-0007 korunur: callback içinde açma/kapama yok.
- [x] Testler: (a) 16 kHz reddedilince ikinci basışta `sd.InputStream` **bir kez**
      çağrılır; (b) cihaz değişince yeniden 16 kHz denenir; (c) Windows'ta ilk
      denemede `extra_settings` WASAPI ayarı taşır.

## Faz 3 — Tuş olayla dinlenir

- [x] `_run_windows`: `keyboard.on_press_key(self._key, ...)` ve
      `on_release_key(...)`; `run()` yalnız `_running` bayrağını bekler,
      `stop()` kancaları `keyboard.unhook(...)` ile söker.
- [x] Basılı tutulan tuşun otomatik tekrar olayları tek `hotkey_pressed`
      verir (`_is_key_down` korunur). `pause()` / `resume()` aynı anlamda kalır.
- [x] `set_key()` eski kancaları söküp yenilerini kurar.
- [x] `resume()`'daki tek seferlik `keyboard.is_pressed()` **kalır**: duraklatma
      sırasında basılı tutulan tuşun bırakılışını yanlışlıkla "basış" saymamak için.
- [x] Testler: kancalara verilen geri çağrılar elle tetiklenir → tekrar eden
      basış tek sinyal; duraklatılmışken sinyal yok; `stop()` kancaları söker;
      `set_key()` sonrası yeni tuş çalışır. Mevcut yoklama testleri
      (`tests/test_hotkey_worker.py`) yeni davranışa çevrilir — **replace, don't layer**.

## Faz 4 — Ön-kayıt tamponu (kullanıcı kararı)

⏸️ **Faz 1 ölçümü ve kullanıcı kararı olmadan başlanmaz.**

Seçenekler:
- **A — Yapma.** Faz 2–3 sonrası basış → ilk ses parçası < ~100 ms ölçülürse
  ve kesilen hece şikâyeti yoksa önerilen budur.
- **B — Mikrofon Katib açıkken sürekli açık**, son ~300 ms halka tamponda;
  basışta tampon kaydın başına eklenir. Bedel: sürekli "mikrofon kullanımda"
  simgesi; ⚠️ takılı cihaz değişikliği için PortAudio yeniden başlatılırken
  stream durdurulup açılmalı (`refresh_devices()` bugün açık stream varken
  yeniden başlatmayı atlıyor — ADR-0007'yle birlikte tasarlanmalı).

---

## Bilinçli olarak YAPILMAYACAKLAR

- **Daha iyi yeniden örnekleme kütüphanesi** (`soxr`, `scipy`). Faz 2 16 kHz'i
  doğrudan alınca yeniden örnekleme çoğu cihazda gereksizleşir; yeni paket yok.
- **WASAPI özel (exclusive) mod.** Diğer uygulamaların sesini keser.
- **Ayarlara "ön-kayıt süresi" seçeneği.** Faz 4 yapılırsa sabit değer yeter.

## Test stratejisi

Her fazın testi yukarıda. ⚠️ **Kırmızı kanıtı:** her yeni test bugünkü kodla
kırmızı olmalı. Gerçek gecikme iddiası yalnız Windows ölçümüyle yapılır.

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| `auto_convert` bazı sürücülerde hata verir | Orta | Mevcut geri dönüş yolu korunuyor; hatırlanan hız sonraki basışları tek denemeye indiriyor |
| `keyboard` kancası yönetici olmayan oturumda yükseltilmiş pencerelerde çalışmaz | Orta | Yoklama da aynı kısıtı taşıyor (aynı kütüphane); davranış değişmez |
| Kanca thread'inden sinyal yayılması | Düşük | Qt sinyali thread'ler arası kuyruklu; bugün de worker thread'inden yayılıyor |

## Efor

Faz 1: 30 dk · Faz 2: 1 sa · Faz 3: 1,5 sa · Faz 4 (B seçilirse): 3+ sa

---

## Yürütme günlüğü

### 2026-10-01 — Faz 1–3 uygulandı

**Faz 1:** `AudioWorker` her kayıtta bir kez `First audio after N ms` logluyor
(`start_recording()` → ilk PortAudio callback'i). ⚠️ Ölçüm tuşa basıştan değil
`start_recording()`'den başlıyor; tuş gecikmesi Faz 3 ile zaten kalktı.
Callback yalnız kuyruğa yazıyor (plan 0004). Windows ölçümü **bekleniyor**.

**Faz 2:** `PortAudioSource.start()` denemeleri sırayla yapıyor: hatırlanan
ayar → (Windows) `WasapiSettings(auto_convert=True)` ile 16 kHz → 16 kHz →
cihazın kendi hızı. Açan ayar `_working`'te hatırlanıyor, cihaz değişince
unutuluyor; yalnız bellekte. Geri dönüş olursa `Microphone opened at N Hz`
loglanıyor. Plan dışı ek: oluşturulup `start()`'ta düşen stream artık
kapatılıyor (önceden sızıyordu).

**Faz 3:** Windows'ta `keyboard.on_press_key` (ana tuş) + her kombinasyon
parçası için `on_release_key`; basışta değiştirici tuşların basılı olduğu
`keyboard.is_pressed` ile doğrulanıyor. Herhangi bir parçanın bırakılması
kaydı bitiriyor (yoklamanın davranışıyla aynı). `set_key()` çalışırken
kancaları taşıyor, `stop()` sonrası `run()` kancaları söküyor. Kanca kurulamazsa
`osd.hotkey_failed`. Artık hiç yayılmayan `osd.keyboard_error` 11 dil
dosyasından ve ölü `_is_pressed()` / `_is_key_down_pynput` kaldırıldı.
⚠️ Plandan sapma: ayarlar penceresi `ctrl+shift+K` gibi **kombinasyonlara** izin
verdiği için tek `on_press_key` yetmedi; tasarım kombinasyonları kapsayacak
şekilde genişletildi.

**Testler:** `tests/test_audio_worker.py::TestStartLatency`,
`tests/test_portaudio_source.py::TestOpenInOneAttempt` (5),
`tests/test_hotkey_worker.py::TestWindowsKeyHooks` (8). Yoklamayı sınayan
eski testler (`TestKeyRepeatPrevention`, `TestRunKeyboardError`,
`TestRunSignalEmission`, `TestRunOuterCrash`, `test_run_ignores_keys_when_paused`)
silindi — replace, don't layer. Kırmızı kanıtı: yeni testlerin hepsi
değişiklikten önce kırmızıydı; "başlatılamayan stream kapatılır" testi düzeltme
geçici geri alınarak ayrıca kırmızıya döndürüldü.

⚠️ **Windows'ta doğrulanması gerekenler:** `keyboard` kanca geri çağrısı içinde
`is_pressed` değiştirici durumunu doğru veriyor mu (konteynerde `keyboard`
kancası kök yetkisi istiyor, denenemedi); `auto_convert` gerçek sürücüde
16 kHz açıyor mu (log'da `Microphone opened at` satırı **görünmemeli**).
