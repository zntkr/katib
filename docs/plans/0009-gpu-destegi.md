# Plan 0009 — GPU Desteği (isteğe bağlı hızlandırma)

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **KARAR BEKLİYOR** — Faz 1 bitti (2026-10-03, kod çalışma ağacında);
Faz 2 ve Faz 3 proje sahibinin kararını bekler.
**Kullanıcı verisi değişikliği:** YOK — yalnız yeni bir ayar anahtarı
(`compute_device`, varsayılan `auto`); CONTEXT.md → Mimari Kurallar #8'e göre onay
gerektirmez. `compute_type`'ın anlamı ve varsayılanı değişmedi.
**Öncelik:** 🟠 Orta-yüksek — hedef macOS diktesine yakın kalite; bunun gerektirdiği
büyük model CPU'da dikte için fazla yavaş.
**Tarih:** 2026-10-03
**İlgili belgeler:** ADR-0010 (karar ve ölçümler), ADR-0002 (çevrimdışı),
`docs/hiz-dogruluk-incelemesi-2026-10-01.md` ("Bilinçli olarak önerilmeyenler"),
CONTEXT.md → "GPU Hızlandırma"

---

## Neden bu plan

`workers/transcription_worker.py` cihazı `cpu` olarak sabitliyordu. Proje sahibinin
makinesinde `medium` CPU'da 3–6 saniye, aynı model RTX 4080'de 0,2–0,6 saniye sürdü
(ölçümler ve koşulları: ADR-0010). CPU'da iş parçacığı sayısını artırmak kazanç
vermedi.

---

## Devralma notu

```bash
# Faz 1 BİTTİYSE: karar modülü var, worker cihazı seçiyor
ls core/gpu.py
grep -n "_open_model\|_gpu_compute_type" workers/transcription_worker.py
python -m pytest -q tests/test_gpu.py
python -m pytest -q tests/test_transcription_worker_logic.py -k "Device or Gpu"
# Faz 2 BAŞLAMADIYSA: paketleme GPU kitaplıklarını hâlâ dışlıyor
grep -n "CPU-ONLY" Katib.spec
# Faz 3 BAŞLAMADIYSA: ayar ekranında cihaz seçimi yok
grep -n "compute_device" ui/settings_dialog.py   # çıktı boş
```

**Ortam**
- Testler: `python -m pytest -q`; referans Windows CI. Testler GPU'ya bağlı değildir
  (`tests/conftest.py::_no_gpu`).
- Gerçek GPU ile deneme için geliştirme ortamında `nvidia-cublas-cu12` pip paketi
  kurulu olmalı; `core/gpu.py` onu `site-packages/nvidia/*/bin` altında bulur.
- ⚠️ Proje sahibinin makinesinde CUDA Toolkit **13** kurulu; CTranslate2 4.7.1
  CUDA **12** ister, o kurulum işe yaramaz.

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| GPU'nun yeri | İyileştirme, gereksinim değil; CPU her zaman son çare | ADR-0010. GPU'suz kullanıcı bugünkünden kötü duruma düşmemeli |
| Karar noktası | `core/gpu.py::unavailable_reason()` | Tek yer; neden log'a yazılır |
| Ayar | `compute_device` = `auto` \| `cpu` \| `cuda`, varsayılan `auto`, ekranda görünmez | Varsayılan doğru olmalı; bozuk bir kart için kaçış yolu `settings.json`'da |
| GPU hesap tipi | Otomatik: `float16`, yoksa `float32` | `compute_type` ayarına dokunmamak (kural #8) |
| Gereken kitaplıklar | Yalnız `cublas64_12.dll` + `cublasLt64_12.dll` | Ölçüldü: cuDNN yüklenmiyor |
| CPU'ya dönüş noktaları | Yükleme, ısınma, dikte anı (aynı kayıt yeniden çevrilir) | Üçü de gerçek dünyada görülen hata anları; üçüncüsü olmazsa GPU'lu kullanıcı CPU'lu kullanıcıdan kötü duruma düşebilir |
| **Kitaplıklar kullanıcıya nasıl ulaşır** | **kullanıcıya sor** (Faz 2) | Paket boyutu ve çevrimdışı ilkesi arasında ürün kararı |
| **Ayar ekranında cihaz seçimi** | **kullanıcıya sor** (Faz 3) | CONTEXT.md "Aşırı UI" ilkesi ile görünürlük arasında ürün kararı |

---

## Faz 1 — Çalışma zamanı: varsa GPU, yoksa CPU

- [x] `core/gpu.py`: `candidate_dirs`, `library_dir`, `unavailable_reason`, `compute_type`.
- [x] `core/settings.py`: `compute_device` anahtarı ve doğrulaması.
- [x] `TranscriptionWorker`: `_gpu_compute_type`, `_open_model`; `_load_model(allow_gpu)`;
      ısınma başarısızsa CPU'ya dönüş; dikte anında GPU hatasında CPU'da yeniden deneme.
- [x] `tests/conftest.py::_no_gpu`: testler makinenin GPU'sundan bağımsız.
- [x] Gerçek donanımda doğrulama (Yürütme günlüğü).

## Faz 2 — Kitaplıkların dağıtımı (karar bekliyor)

Bugün `Katib.spec` GPU kitaplıklarını bilinçli dışlıyor; paketlenmiş uygulama GPU'yu
ancak kitaplıklar `PATH`'te ise kullanır. Seçenekler:

| Seçenek | Artı | Eksi |
|---|---|---|
| A. Ayrı "GPU" kurulum paketi (cuBLAS gömülü, +~770 MB) | Kod değişmez (`core/gpu.py` paketin içine zaten bakıyor); çevrimdışı kurulum | İki paket üretilir ve bakılır |
| B. Uygulama içinden isteğe bağlı indirme (modeller gibi) | Tek küçük paket; isteyen indirir | Yeni indirme akışı, yeni veri klasörü (kural #8: açık onay), 11 dilde metin |
| C. Paketleme yok | Sıfır iş | Yalnız CUDA 12 Toolkit kurmuş kullanıcılar yararlanır |

- [ ] Proje sahibi seçer; seçime göre bu faz ayrıntılandırılır.

## Faz 3 — Ayar ekranı (karar bekliyor)

- [ ] `compute_device` ekranda gösterilsin mi? Gösterilirse 11 dil dosyasına etiket
      ve değişince model yeniden yükleme gerekir.
- [ ] GPU etkinken "Hassasiyet" (`compute_type`) seçimi etkisizdir; ya devre dışı
      gösterilir ya da GPU seçenekleri (`COMPUTE_TYPE_OPTIONS_CUDA`) sunulur. İkincisi
      `compute_type`'ın anlamını değiştirir → kural #8 onayı.

## Faz 4 — Doğruluk ölçümü ve varsayılan model

- [ ] `scripts/olcum.py`'ye cihaz seçimi; proje sahibinin kayıtlarıyla `small` /
      `medium` / `large-v3` kelime hata oranı ve süre (plan 0007 Faz 1b ile aynı kayıtlar).
- [ ] Sonuca göre GPU'lu makinede önerilen model.

---

## Bilinçli olarak YAPILMAYACAKLAR

- **GPU'yu zorunlu kılmak** ya da GPU yokken hata göstermek (ADR-0010).
- **Kendiliğinden indirme.** Kitaplıklar ancak açık onayla iner (ADR-0002).
- **cuDNN paketlemek.** Gerekmiyor (ölçüldü).
- **AMD/Intel GPU desteği.** CTranslate2 desteklemiyor; başka motor gerektirir.
- **Canlı transkripsiyon.** Ayrı bir karar; bu planın kapsamı dışında.

## Test stratejisi

- `tests/test_gpu.py` (14): kitaplık klasörünü bulma (tam / eksik kurulum), aday
  klasörler (pip paketi, paketlenmiş uygulama, `PATH`), kullanılamama nedenleri
  (GPU yok, kitaplık yok, sorgu hatası), arama yoluna tek sefer ekleme, hesap tipi.
- `tests/test_transcription_worker_logic.py::TestDeviceSelection` (8): `auto` GPU'yu
  kullanır; neden log'u; `cpu` ayarı GPU'ya sormaz; istenen GPU yoksa uyarı; yükleme
  hatasında CPU; ısınma hatasında CPU; CPU ısınma hatasında yeniden yükleme yok;
  sonraki yükleme GPU'yu yeniden dener.
- `…::TestGpuFailureDuringDictation` (3): GPU hatasında kayıt CPU'da yeniden çevrilir;
  CPU da başarısızsa hata; CPU hatası yeniden denenmez.
- `tests/test_config.py` (5): `compute_device` varsayılanı, geçerli değerler, geçersiz değer.

**Kırmızı kanıtı:** `core/gpu.py` yokken `tests/test_gpu.py` toplanamadı
(`ImportError`). Modül varken ama worker değişmeden önce `TestDeviceSelection`'dan 6,
`TestGpuFailureDuringDictation`'dan 1 test kırmızıydı; kalan 4'ü doğası gereği o
gün de yeşildi (CPU davranışını koruyan testler).

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| GPU yanlış sonuç üretir ama hata vermez (bazı eski kartlarda `float16`) | Orta | `compute_device: "cpu"` kaçış yolu; Faz 3'te görünür ayar |
| CTranslate2 güncellenince gereken kitaplıklar değişir (ör. cuDNN geri gelir) | Orta | Isınma başarısız olur ve CPU'ya dönülür; `REQUIRED_DLLS` yorumunda ölçülen sürüm yazılı |
| Isınma hatasında modelin iki kez yüklenmesi açılışı uzatır | Düşük | Yalnız bozuk GPU kurulumunda olur; log nedeni söyler |
| GPU kitaplıkları yüklenince bellek kullanımı artar (~770 MB DLL) | Düşük | Yalnız GPU kullanılırken |

## Efor

Faz 1: 3 sa · Faz 2: A 1–2 sa, B 1 gün · Faz 3: 2 sa · Faz 4: proje sahibinin kayıtlarına bağlı

---

## Yürütme günlüğü

### 2026-10-03 — Faz 1 uygulandı

`core/gpu.py` yazıldı; `TranscriptionWorker` cihazı `_open_model` ile seçiyor.
Kullanılmayan `DEVICE` sabiti kaldırıldı.

**Testler:** tam takım 666 geçti, 1 kırmızı. Kırmızı olan
(`tests/test_main.py::TestHandleException::test_crash_dump_masks_string_locals`)
bu değişiklikten **önce de** kırmızıydı (taban: 636 geçti, 1 kırmızı; Python 3.14.4).
Bu planla ilgisi yok.

**Gerçek donanım** (RTX 4080, `medium`, 3,4 sn'lik sentetik klip, uygulamanın kendi
yükleme ve çevirme yolu, arayüz ve mikrofon olmadan):

| Durum | Log | Dikte süresi |
|---|---|---|
| `auto` | `Loading (cuda/float16)`, `Warm-up done (531 ms)` | 305 ms, 299 ms |
| `compute_device: cpu` | `Loading (cpu/int8)` | 6413 ms |
| Kitaplıklar arama yolunda değil | `Warm-up failed: Library cublas64_12.dll is not found…` → `GPU could not run the model, switching to CPU` → `Loading (cpu/int8)` | 6476 ms, hata yok |

⚠️ Denenmedi: paketlenmiş uygulama (`dist\Katib\Katib.exe`), dikte anında gerçek bir
GPU hatası (yalnız testte), RTX 4080 dışında bir kart.
