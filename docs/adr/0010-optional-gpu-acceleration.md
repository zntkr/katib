# ADR-0010: İsteğe Bağlı GPU Hızlandırma

## Durum
Kabul edildi (2026-10-03). `docs/hiz-dogruluk-incelemesi-2026-10-01.md`'deki
"GPU (CUDA) desteği bilinçli olarak önerilmez" maddesinin yerini alır.

## Bağlam
1 Ekim incelemesi GPU desteğini "amaca hizmet etmeden karmaşıklık ve paket boyutu
ekler" diye dışarıda bırakmıştı. 3 Ekim'de proje sahibi hedefi netleştirdi:
Windows'ta macOS diktesine yakın kalite. Bu, `small`'dan büyük bir model demek ve
büyük model CPU'da dikte için fazla yavaş.

Proje sahibinin makinesinde ölçüldü (i7-14700KF, RTX 4080 16 GB, CTranslate2 4.7.1,
faster-whisper 1.2.1, uygulamanın `TRANSCRIBE_OPTIONS`'ı; klipler sentetik konuşma,
yani **yalnız hız** ölçüldü, doğruluk değil):

| Model | Cihaz | 3,4 sn'lik klip | 15,9 sn'lik klip |
|---|---|---|---|
| small | CPU int8 | 1065 ms | 2105 ms |
| medium | CPU int8 | 3458 ms | 6424 ms |
| medium | GPU float16 | 179 ms | 601 ms |

CPU'da iş parçacığı sayısını artırmak (8, 16, 28) kazanç vermedi. CPU süreleri
gürültülüydü: aynı ayar başka bir ölçümde yaklaşık iki kat yavaş çıktı.

## Karar
GPU bir **iyileştirmedir, gereksinim değildir**. Katib GPU'yu kullanabiliyorsa
kullanır; kullanamıyorsa GPU desteğinden önceki gibi CPU'da çalışır.

- **Tek karar noktası:** GPU'nun kullanılıp kullanılamayacağına yalnız
  `core/gpu.py` karar verir (`unavailable_reason()`): bir NVIDIA GPU var mı ve CUDA
  kitaplıkları bulunuyor mu. Kullanılamıyorsa nedeni log'a yazılır
  (Deterministic Specificity).
- **Ayar:** `compute_device` = `auto` (varsayılan) | `cpu` | `cuda`. `auto` ve
  `cuda` aynı yolu izler; fark yalnız log seviyesindedir (`cuda` istenip
  kullanılamazsa uyarı). Ayar şimdilik ayarlar ekranında **görünmez**.
- **CPU her zaman son çaredir.** Üç noktada GPU'dan CPU'ya dönülür:
  1. Model GPU'ya yüklenemezse (ör. ekran belleği yetmez).
  2. Model yüklenir ama ısınma transkripsiyonu başarısız olursa. CUDA kitaplıkları
     tembel yüklenir; eksik kitaplık ancak ilk çalıştırmada ortaya çıkar.
  3. Dikte sırasında GPU hata verirse (ör. bir oyun ekran belleğini doldurur):
     model CPU'ya yeniden yüklenir ve **aynı kayıt** yeniden çevrilir.
  Bir sonraki model yüklemesi GPU'yu yeniden dener.
- **Hesap tipi:** GPU'da otomatik seçilir (`float16`, kart desteklemiyorsa
  `float32`). `compute_type` ayarı CPU ayarı olarak kalır; anlamı ve varsayılanı
  değişmedi.
- **Gereken kitaplıklar:** yalnız `cublas64_12.dll` ve `cublasLt64_12.dll`
  (yaklaşık 770 MB). Ölçülerek doğrulandı: tam bir transkripsiyon cuDNN alt
  kitaplıklarını yüklemiyor; yalnız cuBLAS arama yolundayken `float16`, `float32`
  ve `int8_float16` çalışıyor. Kitaplık yoksa CTranslate2 çökmüyor, yakalanabilir
  bir hata veriyor.
- **Ağ yok:** GPU desteği hiçbir şey indirmez (ADR-0002).

## Reddedilen ya da ertelenen alternatifler
- **CPU'da kalıp ayar kurcalamak:** Ölçüldü; iş parçacığı sayısı kazanç vermedi,
  `medium` CPU'da 3–6 saniye sürüyor.
- **C#'a yeniden yazım (Whisper.net / whisper.cpp):** Atılacak bir denemeyle
  ölçüldü (`medium`, aynı klipler, aynı kart): CUDA 245 / 1463 ms, Vulkan
  528 / 1266 ms, CPU 16 iş parçacığıyla 4186 / 6066 ms. Artısı: Vulkan ile NVIDIA
  dışı ve eski kartlar, yerel Windows arayüzü, az bağımlılık. Eksisi: aynı kartta
  1,4–2,4 kat yavaş ve tam yeniden yazım. Proje sahibi 2026-10-03'te Python'a GPU
  eklemeyi seçti; yeniden yazım kararı verilmedi.
- **cuDNN'i de paketlemek:** Gereksiz (yukarıdaki ölçüm); yaklaşık 1 GB ek yük olurdu.

## Sonuçlar
- CTranslate2 GPU'yu yalnız NVIDIA CUDA ile kullanır. AMD/Intel kartlarda ve CUDA
  12'nin desteklemediği eski NVIDIA kartlarda Katib CPU'da kalır.
- GPU'ya dokunan hiçbir kod GPU'yu **zorunlu** kılamaz: her yeni GPU yolu CPU'ya
  dönüşünü ve onun testini de getirir.
- Testler makinenin GPU'suna bağlı olamaz: `tests/conftest.py::_no_gpu` GPU'yu
  varsayılan olarak "kullanılamaz" yapar; GPU testi isteyen test bunu kendisi açar.
- Kurulum paketi bugün GPU kitaplıklarını **içermez** (`Katib.spec` onları bilinçli
  dışlıyor). Paketlenmiş uygulama GPU'yu ancak kitaplıklar `PATH`'te ise kullanır.
  Kitaplıkların kullanıcıya nasıl ulaşacağı açık karardır: plan 0009 Faz 2.
- Konuşurken canlı transkripsiyon bu kararın kapsamı dışındadır; inceleme
  belgesindeki "önerilmez" notu onun için geçerliliğini korur.
