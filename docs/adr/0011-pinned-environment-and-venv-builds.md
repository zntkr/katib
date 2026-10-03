# ADR-0011: Tek Python Sürümü, Sabitlenmiş Bağımlılıklar, Sanal Ortamdan Derleme

## Durum
Kabul edildi (2026-10-03).

## Bağlam
Katib'in çalıştığı ve derlendiği ortam hiçbir yerde tanımlı değildi:

- `requirements.txt` sürümsüzdü, kilit dosyası yoktu.
- CI Python 3.11 kullanıyordu; proje sahibinin makinesinde 3.11, 3.12 ve 3.14 kurulu,
  derleme ise genel (paylaşılan) 3.14 ortamından yapılıyordu. Yani testler, kullanıcıya
  giden sürümden farklı bir yorumlayıcıda koşuyordu.
- `Katib.spec` `hooks/rthook_dll_paths.py`'yi istiyordu, `hooks/` ise `.gitignore`'daydı:
  depoyu yeni çeken biri derleyemezdi. `Katib.iss` de depoda değildi.
- `build.bat` yorumlayıcının yolunu sabit yazıyordu (`C:\Users\ASUS\...`).
- `CONTEXT.md` `.gitignore`'da listeliydi (izleniyordu, ama tek bir `git rm --cached`
  ile sessizce düşerdi).

Bunun somut bedelleri 2026-10-03'te görüldü:

1. `python main.py` 3.12'ye gitti ve `No module named 'faster_whisper'` ile model yüklenemedi.
2. **Gizlilik hatası.** `tests/test_main.py::TestHandleException::test_crash_dump_masks_string_locals`
   CI'da (3.11) yeşil, 3.14'te kırmızıydı. Neden: Python 3.13'ten beri `frame.f_locals`
   sözlük değil vekil nesne döndürür; `mask_text` onu tanımadığı için çökme kaydına yerel
   değişkenler (dikte metni dahil) maskelenmeden yazılıyordu. Paketlenen sürüm 3.14 ile
   derlendiği için **kullanıcıya giden sürüm etkileniyordu**, CI ise göremiyordu.
   `main.py`'de düzeltildi (`dict(frame.f_locals)`).
3. `build.bat`'ın Inno Setup adımı sözdizimi hatasıyla duruyordu: blok içindeki `echo`
   satırlarında kaçışsız parantez (`. was unexpected at this time.`).
4. **Testler tanımsız bir eklentiye yaslanıyordu.** Genel ortamda `pytest-qt` kuruluydu,
   `requirements-dev.txt`'te ise yoktu. Temiz `.venv`'de `tests/test_dialogs.py`'den 3 test
   sökümde hata verdi: `SettingsDialog.show()` içindeki `QTimer.singleShot(0, btn.setFocus)`,
   pencere yok edildikten sonra silinmiş düğmeyi çağırıyordu; `pytest-qt` bu hatayı yutuyordu.
   Kök neden uygulamadaydı ve orada düzeltildi: zamanlayıcıya bağlam nesnesi verildi
   (`QTimer.singleShot(0, btn, btn.setFocus)`), Qt nesne yok olunca çağrıyı düşürüyor.

## Karar
- **Tek Python sürümü.** `.python-version` dosyasında yazar (bugün `3.14`). CI ve
  `build.bat` sürümü oradan okur; başka hiçbir yerde sürüm yazılmaz.
- **Sabitlenmiş bağımlılıklar.** Doğrudan bağımlılıklar `requirements.txt` ve
  `requirements-dev.txt` içinde `==` ile; onların çektiği her paket `constraints.txt`
  içinde. Kurulum her zaman `-c constraints.txt` ile yapılır. GPU kitaplığı isteğe
  bağlıdır: `requirements-gpu.txt` (ADR-0010).
- **Her şey projenin kendi sanal ortamında (`.venv`).** `build.bat` ortamı yoksa kurar,
  varsa sabitlenmiş sürümlere eşitler ve yalnız oradan derler. Genel Python ortamından
  çalıştırma ve derleme desteklenmez.
- **Derlemenin istediği her dosya depodadır:** `hooks/` ve `Katib.iss` dahil.

## Reddedilen Alternatifler
- **uv / Poetry / pip-tools:** Yeni bir araç bağımlılığı. `pip` + `constraints.txt` aynı
  güvenceyi ek araç olmadan veriyor.
- **`pyproject.toml`:** Katib bir Python paketi olarak dağıtılmıyor; kurulacak bir paket yok.
- **CI'ı 3.11'de bırakıp derlemeyi 3.11'e çekmek:** Geçerli bir seçenekti. 3.14 seçildi,
  çünkü 2026-10-03'te doğrulanan her şey (testler, GPU, ölçümler) o yorumlayıcıdaydı.

## Sonuçlar
- **Sürüm değiştirmek:** `requirements*.txt`'i düzenle → temiz bir `.venv` kur → testleri
  çalıştır → `constraints.txt`'i o ortamın `pip freeze` çıktısıyla yenile.
- **Python sürümünü değiştirmek:** yalnız `.python-version`; ardından aynı adımlar.
- `constraints.txt` Windows + Python 3.14'te çalışan ortamdan üretildi. Başka platformda
  doğrulanmadı.
- Yeni bir test eklentisi ya da araç gerekiyorsa önce `requirements-dev.txt`'e ve
  `constraints.txt`'e girer; genel ortama kurulmuş bir paket "var" sayılmaz.
- `Katib.spec`'teki dışlama listesi 95 girdiden 55'e indi. Çıkarılan 40 girdi (torch, pandas,
  fastapi, kubernetes…) genel ortamdaki ilgisiz paketler içindi ve sanal ortamda etkisizdi.
  Kalanlar gerçekten bir şey kesiyor: 39 PySide6 alt modülü, 15 standart kitaplık modülü
  ve `hf_xet`.

## Doğrulama (2026-10-04)
- Temiz `.venv` (Python 3.14.4) sabitlenmiş dosyalardan kuruldu: 54 paket, `constraints.txt`
  ile birebir aynı; `pip check` temiz.
- Testler `.venv`'de: 667 geçti. (Genel ortamda da 667.)
- `.venv`'den derleme: 328 MB, 744 dosya. Dışlama listesi budanmadan önce ve sonra iki
  derleme dosya adı ve boyut olarak birebir aynı çıktı. Genel ortamdan yapılan eski derleme
  775 dosyaydı; fark, o ortamdan sızan ilgisiz paketlerdi (chardet, markupsafe, attrs, yarl…).
- ⚠️ Denenmedi: derlenen `Katib.exe`'nin çalıştırılması, `build.bat`'ın baştan sona koşması
  (akışı ağır komutlar `echo` ile değiştirilerek sınandı), Inno Setup adımı, yeni CI koşusu.
