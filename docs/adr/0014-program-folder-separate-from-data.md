# ADR-0014: Program Klasörü Veri Klasöründen Ayrıdır; Kaldırıcı Kullanıcı Verisini Silmez

## Durum
Kabul edildi (2026-10-04).

## Bağlam
ADR-0009 tüm kullanıcı verisini `%LOCALAPPDATA%\Katib` altında topladı: `settings.json`,
`Models\` (3 GB'a kadar), `Logs\`. Kurulum betiği (`Katib.iss`) ise programı **aynı klasöre**
kuruyordu (`DefaultDirName={localappdata}\Katib`) ve kaldırıcısı o klasörü kökten siliyordu
(`[UninstallDelete] Type: filesandordirs; Name: "{app}"`). Satırın üstündeki yorum, verinin
`%USERPROFILE%\.katib_app` altında korunduğunu söylüyordu; ADR-0009'dan beri bu yanlıştı.

Sonuç: Katib'i Windows'tan kaldıran kullanıcı, sorulmadan ayarlarını ve indirdiği bütün
modelleri kaybediyordu. Proje sahibinin makinesinde durum (2026-10-04): 1.0.0 kurulu,
aynı klasörde 2,9 GB model, kaldırma kaydı oradaki `unins000.exe`'yi gösteriyor.

Inno Setup belgeleri `[UninstallDelete]` için tam bu durumu uyarır: `{app}` altındaki her
şeyi silmek, kullanıcı verisi oradaysa "felaket" olur.

## Karar
1. **Program ve veri ayrı klasörlerdedir.**
   - Program: `{autopf}\Katib` → kullanıcı başına kurulumda `%LOCALAPPDATA%\Programs\Katib`
     (Windows'un yönetici hakkı istemeyen kurulumlar için ayırdığı yer).
   - Veri: `%LOCALAPPDATA%\Katib` (ADR-0009, değişmedi).
2. **Program her zaman o tek klasöre kurulur.** Kurulum klasör sormaz
   (`DisableDirPage=yes`) ve eski kurulumun klasörünü yeniden kullanmaz
   (`UsePreviousAppDir=no`; 1.0.0'ın klasörü veri klasörüydü). Bunlar Inno Setup'ın hazır
   ayarlarıdır; betikte klasör denetleyen kod yoktur.
3. **Kaldırıcı yalnız kurulumun koyduğu dosyaları kaldırır.** `[UninstallDelete]` bölümü
   yoktur; betikte kendi başına dosya silen kod yoktur. Kaldırma bitince veri klasörünün
   yeri kullanıcıya söylenir; silmek kullanıcının kendi işidir. Betikteki tek kod bu
   bildirimdir.
4. **Betik veri klasörünün yerini tek satırda bilir** (`#define DataDir`) ve bu satır
   `core/settings.py::get_app_data_dir()` ile aynı klasörü göstermek zorundadır
   (`tests/test_installer.py`).

## Reddedilen Alternatifler
- **Yalnız `[UninstallDelete]` satırını silmek, programı yerinde bırakmak:** Program dosyaları
  kullanıcı verisiyle aynı klasörde kalırdı; `_internal\` ile `Models\` yan yana durur ve
  bir sonraki "temizlik" hatası yine veriyi vururdu. Ayrıca Inno Setup varsayılan olarak
  eski kaldırma kaydının **üzerine ekler** (`UninstallLogMode=append`); 1.0.0'ın silme
  kaydının aynı klasöre yapılan yükseltmeden sonra da geçerli kalması beklenir
  (⚠️ belgelerden çıkarım, çalıştırılarak gösterilmedi).
- **Klasör sayfasını gösterip veri klasörünü kodla reddetmek:** İlk sürümde böyle yazıldı
  (klasörü karşılaştıran bir işlev, öneriyi değiştiren ve seçimi reddeden iki olay) ve aynı
  gün kaldırıldı. Kaldırıcı zaten yalnız kendi kurduğunu sildiği için veri klasörüne kurulum
  artık veri kaybına yol açmıyor; kod, kalkmış bir tehlikeye karşı ikinci bir önlemdi.
  Tepsi uygulaması için klasör seçtirmenin bir yararı da yok: büyük olan modellerdir ve
  onların yeri uygulamanın içinden seçilir.
- **Inno Setup'ın varsayılanları (ilk kurulumda sor, yükseltmede eski klasörü kullan):**
  Yaygın kullanım budur; ama 1.0.0'dan yükseltenleri veri klasöründe bırakırdı ve bunu
  aşmak için yine özel kod gerekirdi.
- **Veriyi başka yere taşımak (ör. `%APPDATA%`):** ADR-0009'un kararını ve gerekçesini
  (büyük modeller dolaşan profile girmemeli) bozar; her kullanıcıda gigabaytlarca dosya
  taşımak gerekir; kurumsal kılavuzdaki yol değişir.
- **`{commonpf}` (Program Files):** Yönetici hakkı ister; `PrivilegesRequired=lowest`
  kararıyla çelişir.
- **Kaldırırken veriyi de silmeyi sormak:** Silme kodu yeni bir veri kaybı yoludur;
  kaldırıcı yalnız verinin yerini söyler.

## Sonuçlar
- Kullanıcı kurulum klasörünü sihirbazdan seçemez; başka bir klasör yalnız komut satırından
  (`/DIR=`) verilebilir ve her yükseltmede yeniden verilmelidir. Seçim istenirse
  `DisableDirPage` ve `UsePreviousAppDir` birlikte gözden geçirilir.
- `Katib.iss`'e veri klasörüne yazan ya da oradan silen bir satır eklenmez
  (`tests/test_installer.py` dört bölümü denetler).
- **Kurulum, 1.0.0'ın veri klasöründe bıraktığı program dosyalarını silmez** (`Katib.exe`,
  `_internal\`, `unins000.*`, ~335 MB). Yalnız eski sürüm için bir kez çalışacak kod
  yazılmadı (proje sahibi, 2026-10-04); bilinen tek 1.0.0 kurulumu proje sahibinin
  makinesindedir ve orada elle silinir (plan 0011 Faz 2). 1.0.0 başkalarına dağıtıldıysa bu
  karar yeniden düşünülmelidir: o makinelerde eski `unins000.exe` elle çalıştırılırsa veri
  klasörünü hâlâ siler.
- Katib çalışırken kaldırma yapılırsa kullanımdaki dosyalar kalır; kurulumun çalışan Katib'i
  fark etmesi için adlandırılmış bir mutex gerekir (bugün `QSharedMemory` var, Inno Setup onu
  göremez). Bu ADR'nin kapsamında yapılmadı.
