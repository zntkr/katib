# Plan 0015 — Paketlemeye Dışarıdan DLL Sızıntısı (Qt açılışta düşüyor)

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **DOĞRULAMA BEKLİYOR** — Faz 1 bitti; Faz 2'nin derleme kısmı doğrulandı (2026-10-07). Tam açılış ve kurulum sonrası deneme bekleniyor.
**Kullanıcı verisi değişikliği:** YOK
**Öncelik:** 🔴 Yüksek — böyle derlenen paket hiç açılmıyor (kurulumdan sonra ilk satırda düşüyor).
**Tarih:** 2026-10-07
**İlgili belgeler:** ADR-0011 (sabit ortam, `.venv`'den derleme), `Katib.spec`, `build.bat`,
`hooks/rthook_dll_paths.py`

---

## Neden bu plan

`main`'den (Codex ajanının bilgisayarında) derlenip kurulan `Katib.exe` açılışta düştü:

```
File "main.py", line 20, in <module>
ImportError: DLL load failed while importing QtWidgets: Belirtilen yordam bulunamadı.
```

**Sebep:** PyInstaller, Qt6Core'un bağımlılığı `icuuc.dll`'i derleyen bilgisayarın PATH'inde
bulduğu bir **Poppler araç klasöründen** pakete aldı (ICU 78). Bağımsız derlenmiş ICU
fonksiyonlarını sürüm ekiyle verir (`ucnv_open_78`); Qt6Core ise Windows'un kendi ICU'sundaki
eksiz adları ister (`ucnv_open` vb., 20 fonksiyon; PySide6 6.10.2 Windows paketinin içe aktarma
tablosundan okundu). PyInstaller'ın açılış kodu `_internal`'ı DLL aramasında System32'nin
önüne koyduğu için (`rthook_dll_paths.py` de aynı klasörü ilk sıraya ekliyor) yanlış kopya yüklendi.

**Nasıl doğrulandı (2026-10-07, proje sahibinin bilgisayarı, Windows build 26300):**
- Kurulu pakette `_internal\icuuc.dll` ve `_internal\icudt78.dll` var, sürüm `78, 3, 0, 0`.
- `_internal\icuuc.dll`'in adı değiştirilince Katib açıldı.
- Teşhis betiği: Windows'un kendi `icuuc.dll`'i Qt'nin istediği 20 fonksiyonun hepsini veriyor;
  Qt6Core/Gui/Widgets tek başlarına yükleniyor (677 fonksiyonun hiçbiri eksik değil).
- Codex aynı hatayı yeniden üretti; Windows'un doğru ICU'su önce yüklenince QtWidgets açıldı (proje sahibinin aktarımı).
- Elenen hipotezler: yanlış Python/PySide sürümü (sürümler sabitlenenlerle aynı), kökteki
  `msvcp140.dll` 14.51 (yeniden adlandırılınca hata sürdü), Windows önizleme sürümü (sistem
  DLL'lerinde eksik yok).

**Neden testler yakalamadı:** testler kaynaktan çalışır; paket hiç derlenip açılmıyor (CI dahil).

---

## Devralma notu

```bash
# Faz 1 BİTTİYSE: PATH temizliği ve ICU filtresi yerinde, testleri geçiyor
grep -n 'set "PATH=' build.bat
grep -n "_is_icu" Katib.spec
python -m pytest -q tests/test_packaging.py
```

Faz 2 (Windows, PowerShell, derlemeden sonra):

```powershell
Get-ChildItem dist\Katib\_internal -Recurse -Filter icu*.dll   # çıktı BOŞ olmalı
Start-Process dist\Katib\Katib.exe                               # açılmalı
```

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Asıl düzeltme | `build.bat` PyInstaller'ı yalnız Windows klasörleri PATH'teyken çalıştırır | Sızıntı PATH'ten geliyor; bu, ICU dışındaki her araç DLL'ini (Git, Conda, ImageMagick…) de keser. `.venv`'in Python'u tam yoluyla çağrılıyor, PATH'e ihtiyacı yok |
| İkinci güvence | `Katib.spec` hiçbir `icu*.dll`'i pakete almaz | Qt Windows'ta işletim sisteminin ICU'sunu kullanır (Windows 10 1703+); paketteki her ICU kopyası ya gereksiz ya zararlı |
| `rthook_dll_paths.py` | Değişmez | Paketin kendi DLL'lerinin bulunması için gerekli; sorun yanlış DLL'in pakete girmesi |
| CI'da derleme + açılış denetimi | **Ayrı iş, kullanıcı kararı** | Bu planın kapsamı dışında; bu hatayı ve benzerlerini otomatik yakalar |
| Ajan belgeleri (`AGENTS.md`, `CLAUDE.md`) | **Ayrı iş, kullanıcı kararı** | Derleme kuralı CONTEXT.md'de yazılı ama hiçbir ajan o dosyayı kendiliğinden okumuyor |

---

## Fazlar

### Faz 1 — PATH temizliği ve ICU filtresi
- [x] `build.bat`: PyInstaller'dan hemen önce `set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem"`
      (`setlocal` sayesinde betik bitince eski PATH döner).
- [x] `Katib.spec`: `_is_icu()`; elle toplanan binary'lerde ve Analysis sonrası filtrede kullanılıyor.
- [x] `tests/test_packaging.py` (5): PATH PyInstaller'dan önce ve yalnız `%SystemRoot%`; `setlocal`
      önce; spec'in kendi `_is_icu()`'su ICU adlarını tanıyor, diğerlerini tanımıyor; iki filtre de kullanıyor.

### Faz 2 — Windows'ta derleme ve açılış (kullanıcı ya da Windows'ta çalışan ajan)
- [x] Bu daldan `build.bat`; `dist\Katib\_internal` içinde `icu*.dll` yok.
- [ ] `dist\Katib\Katib.exe` açılıyor; kurulum (`installer\`) sonrası da açılıyor.
- [x] Derleme çıktısında PyInstaller'ın "not found" uyarıları önceki derlemeyle karşılaştırılır:
      PATH temizliği gerçekten gereken bir DLL'i dışarıda bırakmamalı.
- [x] ⚠️ PATH'te UPX varsa artık kullanılmaz (`upx=True` yalnız UPX bulunursa çalışır); paket
      biraz büyüyebilir. Bilinçli kabul: UPX Qt DLL'lerini bozabildiği biliniyor.

---

## Bilinçli olarak YAPILMAYACAKLAR

- **Pakete belirli bir ICU sürümü koymak.** Qt Windows'un ICU'su için derlenmiş; başka ICU uyumsuz.
- **`rthook_dll_paths.py`'den kök klasörü çıkarmak.** Sorunu çözmez (PyInstaller'ın açılış kodu
  da aynı şeyi yapıyor) ve paketin kendi DLL'lerini bulmasını bozabilir.

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| Daha önce PATH'ten gelip gerçekten gereken bir DLL artık pakete girmez | Orta | Faz 2'deki "not found" karşılaştırması ve açılış denemesi |
| Windows 10 1703'ten eski sistemde ICU yok | Düşük | Qt 6.10 zaten Windows 10 1809+ istiyor |

## Efor

Faz 1: 1 sa · Faz 2: derleme + 15 dk deneme

---

## Yürütme günlüğü

### 2026-10-07 — Plan açıldı, Faz 1 uygulandı

Teşhis ve kanıtlar yukarıda. Faz 1 testleri: değişiklik geri alınınca 5 testin 5'i kırmızı.
Faz 2 bu konteynerde yapılamaz (Windows exe derlenemiyor).

### 2026-10-07 — Faz 2: derleme doğrulandı (Codex, Windows; proje sahibinin aktarımı)

`abcec1a` (bu dalın Faz 1 commit'i) `build.bat` ile derlendi:
- 708 test geçti.
- Pakette `icu*.dll` yok.
- Gerçek `Katib.exe` QtWidgets hatasını geçti. Tam açılış denenemedi: makinede açık bir Katib
  olduğu için tek örnek kilidi yeni süreci normal biçimde kapattı.
- Yeni "DLL not found" uyarısı yok; eksik Python modülü listesi değişmedi.
- UPX kurulu değil (davranış değişmedi). Kurulum paketi 102,07 MB → 91,76 MB: sızan ICU
  dosyaları (veri dosyası `icudt78.dll` dahil) artık pakette değil.

**Kalan:** açık Katib kapatılıp `dist\Katib\Katib.exe`'nin tam açılışı; kurulum paketiyle kurup açılış.

### 2026-10-07 — Kurulum betiği eski ICU'yu siliyor (plan 0009 Faz 2 PR'ı ile)

v1.1.0 sürüm notları "yeniden kurmak eski `icuuc.dll`'i geride bırakabilir" diye uyarıyordu:
Inno Setup dosyaların üstüne yazar ama eskileri silmez. `Katib.iss` artık kurulumdan önce
`{app}\_internal\icu*.dll` dosyalarını adıyla siliyor (yalnız program klasörü; klasör toptan
silinmez, ADR-0014). Test: `tests/test_packaging.py::TestGpuPackage::test_setup_removes_a_leftover_foreign_icu_and_nothing_else`.
