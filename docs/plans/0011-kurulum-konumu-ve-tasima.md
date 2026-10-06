# Plan 0011 — Kurulum Konumu (kaldırıcı kullanıcı verisini siliyordu)

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **DOĞRULAMA BEKLİYOR** — Faz 1 bitti (2026-10-04, kod çalışma ağacında);
Faz 2 proje sahibinin kendi makinesindeki yükseltmedir.
**Kullanıcı verisi değişikliği:** YOK — kurulum da kaldırma da veri klasörüne yazmaz, oradan
silmez.
**Öncelik:** 🔴 Yüksek — Katib'i Windows'tan kaldıran kullanıcı, sorulmadan ayarlarını ve
indirdiği bütün modelleri kaybediyordu.
**Tarih:** 2026-10-04
**İlgili belgeler:** ADR-0014 (karar), ADR-0009 (veri kökü), `Katib.iss`,
`tests/test_installer.py`

---

## Neden bu plan

`Katib.iss` (commit `eea6f99`):

- satır 13: `DefaultDirName={localappdata}\{#AppName}` — program, veri köküne kuruluyor
  (`core/settings.py::get_app_data_dir()` de aynı klasörü döndürür);
- satır 57: `[UninstallDelete] Type: filesandordirs; Name: "{app}"` — kaldırıcı o klasörü
  içindeki her şeyle siler;
- satır 56'daki yorum verinin `%USERPROFILE%\.katib_app` altında korunduğunu söylüyor;
  ADR-0009'dan beri veri orada değil.

**Nasıl doğrulandı:** betik okunarak ve proje sahibinin makinesine bakılarak (2026-10-04):
`%LOCALAPPDATA%\Katib` içinde `Katib.exe` (15 MB), `_internal\` (317 MB), `unins000.exe`,
`unins000.dat` ile `settings.json`, `Models\` (2,9 GB) ve `Logs\` yan yana duruyor;
Windows'taki kaldırma kaydı oradaki `unins000.exe`'yi gösteriyor.
⚠️ Kaldırıcının veriyi sildiği çalıştırılarak gösterilmedi.

🛑 **Bu makinede, Faz 2 yapılana dek Katib'i Windows'tan kaldırma:** 2,9 GB model ve
ayarlar silinir.

---

## Devralma notu

```bash
# Faz 1 BİTTİYSE: program ayrı klasöre kuruluyor, kaldırıcı hiçbir şey silmiyor
grep -n "^DefaultDirName\|^DisableDirPage\|^UsePreviousAppDir\|UninstallDelete" Katib.iss
.venv/Scripts/python -m pytest -q tests/test_installer.py        # 11 geçer
```

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Program klasörü | `{autopf}\Katib` = `%LOCALAPPDATA%\Programs\Katib` | Yönetici hakkı istemeyen kurulumların Windows'taki yeri; veri kökünün dışında (ADR-0014) |
| Veri klasörü | Değişmez: `%LOCALAPPDATA%\Katib` | ADR-0009; sorun verinin yeri değil, programın oraya kurulmasıydı |
| Klasör seçimi | Yok: program her zaman o klasöre kurulur (`DisableDirPage=yes`, `UsePreviousAppDir=no`) | Hazır iki ayar, sıfır kod; 1.0.0'dan yükselten de aynı yere gelir |
| Kaldırıcı | Yalnız kurulumun koyduğunu kaldırır; verinin yerini söyler | ADR-0014 |
| 1.0.0'ın veri klasöründe bıraktığı program dosyaları | Kurulum silmez; bir kez elle silinir (Faz 2) | Proje sahibi yalnız eski sürüm için bir kez çalışacak kod istemedi (2026-10-04); bilinen tek 1.0.0 kurulumu kendi makinesinde |

⚠️ **Varsayım:** 1.0.0 kurulumu başkalarına dağıtılmadı (sorulduğunda yanıtlanmadı).
Dağıtıldıysa o kullanıcılarda eski kaldırıcı veri klasöründe durmaya devam eder ve elle
çalıştırılırsa veriyi siler; o zaman temizliğin kurulumca yapılması yeniden düşünülmelidir.

---

## Faz 1 — Güvenli konum ve zararsız kaldırıcı

- [x] `Katib.iss`: `DefaultDirName={autopf}\{#AppName}`; `DisableDirPage=yes`;
      `UsePreviousAppDir=no`; `#define DataDir`.
- [x] `[UninstallDelete]` bölümü kaldırıldı; yanlış yorum silindi.
- [x] `[Code]`: yalnız kaldırma bitince verinin yerini söyleyen bildirim.
- [x] `tests/test_installer.py` (11 test); ADR-0014; CONTEXT.md.

## Faz 2 — Proje sahibinin makinesinde yükseltme (elle, bir kez)

- [ ] `%LOCALAPPDATA%\Katib\settings.json` dosyasını başka bir yere kopyala (modeller
      yeniden indirilebilir; ayarlar indirilemez).
- [ ] Katib'i tepsiden kapat. `build.bat` → yeni kurulumu çalıştır. Beklenen: klasör
      sorulmaz; program `C:\Users\<ad>\AppData\Local\Programs\Katib` içine kurulur.
- [ ] Katib açılır, ayarlar ve model yerinde. Windows → "Yüklü uygulamalar"da Katib'in
      konumu yeni klasör. 🛑 Değilse dur; sonraki adımı yapma.
- [ ] `%LOCALAPPDATA%\Katib` içinden yalnız şunları sil: `Katib.exe`, `_internal`,
      `unins000.exe`, `unins000.dat`. Kalması gerekenler: `settings.json`, `Models`, `Logs`.
- [ ] (İsteğe bağlı) Katib'i kaldırıp yeniden kur: kaldırma sonrası `settings.json`,
      `Models`, `Logs` yerinde mi?

---

## Bilinçli olarak YAPILMAYACAKLAR

- **Kurulumun eski program dosyalarını kendisinin silmesi.** Yalnız 1.0.0 için bir kez
  çalışacak kod; yukarıdaki varsayım bozulmadıkça gereksiz.
- **Veri klasörünü taşımak.** ADR-0009 geçerli.
- **Eski kaldırıcıyı çalıştırarak temizlemek.** Veriyi siler.
- **Kaldırırken "veriyi de sil" seçeneği.** Silme kodu yeni bir veri kaybı yoludur.
- **Klasör denetleyen kod.** Yazıldı, aynı gün kaldırıldı (ADR-0014 → Reddedilen Alternatifler).

**Yayımlamadan önce yapılması iyi olanlar** (bu planın dışında): sürüm numarasını yükseltmek
(eski ve yeni kurulum aynı adı taşır: `Katib_Setup_1.0.0.exe`); kurulumun çalışan Katib'i
fark etmesi için adlandırılmış bir mutex ve `AppMutex=` (Katib çalışırken kaldırılırsa
kullanımdaki dosyalar kalır).

## Test stratejisi

- `tests/test_installer.py` betiği **okur** (11 test): veri klasörü koddakiyle aynı; program
  veri klasörüne kurulmuyor; konum `Programs\Katib`; klasör sorulmuyor ve eski klasör yeniden
  kullanılmıyor; `[UninstallDelete]` yok; dört bölümde veri klasörüne dokunan satır yok;
  betikte silme çağrısı yok; tek kod kaldırma bildirimi.
- **Kırmızı kanıtı:** testler önce yazıldı; `eea6f99`'daki betikte 7'si kırmızıydı.
- ⚠️ Betiği okuyan test, kurulumun gerçekte ne yaptığını göstermez; onu Faz 2 gösterir.

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| Yükseltmede program yeni klasöre gitmez (ayarlar beklendiği gibi çalışmaz) | 🟡 Orta | Faz 2'nin üçüncü adımı bunu denetler; elle silme ondan sonra |
| Elle silerken yanlış dosya silinir | 🟡 Orta | Önce `settings.json` yedeği; silinecek dört ad yazılı |
| Güvenlik yazılımı imzasız kurulumu engeller | 🟡 Orta | 2026-10-04'te küçük bir deneme kurulumunda görüldü; kurulumu imzalamak ayrı konu |

## Yürütme günlüğü

### 2026-10-04 — Faz 1

- Testler önce yazıldı; eski betikte 7'si kırmızıydı.
- İlk sürüm fazlaydı: klasör denetleyen kod, kurulumun eski dosyaları silmesi için bir taslak
  ve yedi senaryoluk bir deney betiği içeriyordu. Proje sahibi önce klasör denetimini, sonra
  yalnız eski sürüm için bir kez çalışacak kodu sorguladı; ikisi de çıkarıldı, deney betiği
  silindi. Kalan: iki hazır ayar ve kaldırma bildirimi.
- Inno Setup belgelerinden doğrulananlar (jrsoftware.org/ishelp): `UsePreviousAppDir`
  varsayılanı `yes` (eski klasör yeniden kullanılır); `DisableDirPage`; `{autopf}` yönetici
  olmayan kurulumda kullanıcının program klasörüdür.
- Betik, sahte küçük bir derleme klasörüyle Inno Setup 7'de hatasız derlendi. Tam takım:
  702 geçti.

⚠️ **Denenmedi:** hiçbir kurulum çalıştırılmadı (deneme kurulumunu güvenlik yazılımı
engelledi); gerçek `dist\Katib` ile tam kurulum da derlenmedi.
