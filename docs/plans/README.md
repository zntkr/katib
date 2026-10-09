# Planlar — açık işler haritası

> Bu dosya **yalnız yön tarifidir**. Gerçek bilgi planların kendisindedir;
> her plan kendi kendine yeten bir devir belgesidir. Bir sayıya ya da karara
> ihtiyacın varsa planı aç, buradan alıntılama.

**Son güncelleme:** 2026-10-10 · **15 plan, 4 kapalı, 11 açık.** (0006–0008 hız/doğruluk incelemesinden, 0009 ADR-0010'dan, 0010 ADR-0012'den, 0011 ADR-0014'ten, 0012–0014 2026-10-06 hız incelemesinden açıldı.)

⚠️ Bu tablo elle tutuluyor ve bayatlayabilir. Şüphelendiğinde depodan doğrula:

```bash
python - <<'PY'
import re, pathlib
def katla(s):  # Turkce-guvenli kucultme
    return s.replace("ı","i").replace("I","i").replace("İ","i").lower()
KAPALI = ("kapand", "tamamland", "uyguland")
for p in sorted(pathlib.Path("docs/plans").glob("[0-9]*.md")):
    m = re.search(r"\*\*Durum:\*\*\s*(.+)", p.read_text(encoding="utf-8"))
    d = (m.group(1).strip() if m else "(durum satiri YOK)")[:58]
    if not any(k in katla(d) for k in KAPALI):
        print(f"{p.stem:48} {d}")
PY
```

🛑 `grep -i KAPANDI` **kullanma** — Türkçe `ı/I` katlaması yüzünden kapalı
planı açık gösterebilir; `katla()` bunun içindir.
⚠️ Dosya süzgeci `[0-9]*.md` olmalı: `*.md` bu README'yi de listeler.

---

## Açık planlar

| Plan | Konu | Öncelik | Bağımlılık |
|---|---|---|---|
| [0015](0015-paketleme-dll-sizintisi.md) | Paketlemeye dışarıdan DLL sızıntısı (Qt açılışta düşüyor) | 🔴 ⏸️ Faz 1 ✅, doğrulama bekliyor | Faz 2: Windows'ta derleme + açılış |
| [0011](0011-kurulum-konumu-ve-tasima.md) | Kurulum konumu (kaldırıcı kullanıcı verisini siliyordu) | 🔴 ⏸️ Faz 1 ✅, doğrulama bekliyor | Faz 2: kullanıcının kendi makinesinde yükseltme |
| [0006](0006-kayit-baslangici-gecikmesi.md) | Kayıt başlangıcı: gecikme ve kesilen ilk hece | 🔄 3/4 faz | Faz 4: Windows ölçümü + kullanıcı kararı |
| [0007](0007-sessizlik-katmanlarini-sadelestirme.md) | Sessizlik katmanlarını sadeleştirme (önce ölç) | ⏸️ Faz 1a ✅, kayıt bekliyor | Faz 1b: kullanıcının kayıtları |
| [0005](0005-ses-islerinin-ui-thread-olcumu.md) | Ses işlerinin UI thread'de çalışması | ⏸️ Veri bekliyor | Kullanıcının Windows ölçümü |
| [0008](0008-model-yuklenince-isinma.md) | Model yüklenince ısınma transkripsiyonu | ⏸️ Faz 1 ✅, doğrulama bekliyor | Faz 2: kullanıcının Windows log'u |
| [0009](0009-gpu-destegi.md) | GPU desteği (isteğe bağlı hızlandırma) | ⏸️ Faz 1 ✅, Faz 2: RTX 4080'de çalıştı, model değişimi çökmesi düzeltildi (2026-10-10) | Faz 2: düzeltmeli GPU paketini yeniden yayınla + kartsız makinede deneme |
| [0010](0010-tek-pencereli-arayuz.md) | Tek pencereli arayüz (dashboard'un kaldırılması) | ⏸️ Faz 1–3 ✅, doğrulama bekliyor | Faz 4: kullanıcının gerçek uygulamada denemesi |
| [0012](0012-cozumleme-ayarlari-ve-gecikme-olcumu.md) | Çözümleme ayarları ve uçtan uca gecikme ölçümü | 🟠 ⏸️ Faz 1–2, 5 ✅, ölçüm bekliyor | Faz 3: kullanıcının ölçümü → Faz 4 |
| [0013](0013-large-v3-turbo-modeli.md) | `large-v3-turbo` modeli | 🟠 ⏸️ Karar bekliyor | Model kaynağı ve listedeki yer: kullanıcı kararı |
| [0014](0014-uzun-diktelerde-arka-planda-cozumleme.md) | Uzun diktelerde arka planda çözümleme | 🟠 ⏸️ Faz 1 (kod) ✅, ölçüm bekliyor | `olcum.py --parcali` ölçümü + kullanıcı kararı; Faz 2 için 🛑 0012 Faz 4 |

0001–0004 2026-10-01'de kapandı (aşağıda "Kapalı planlar"). 0006–0008
`docs/hiz-dogruluk-incelemesi-2026-10-01.md`'nin bulgularıdır; 0009 hedefin
netleşmesiyle (ADR-0010) açıldı. 0012–0014 `docs/hiz-incelemesi-2026-10-06.md`'nin
bulgularıdır; aynı incelemeyle 0006 Faz 4'e seçenek C ("ilk basışta uyan, N dk
uyanık kal"), 0007'ye Silero/seviye analizi karşılaştırması eklendi.

---

## İki tür bağımlılık — karıştırma

### 🛑 SERT — bozarsan bir şey kırılır

- **0012 Faz 4 → 0014 Faz 2.** Parçalı ve bütün çözümleme aynı `decode_options`'ı
  kullanmalı; 0014 sabit sözlüğe göre yazılırsa 0012 Faz 4 onu sessizce ayırır ve
  `olcum.py`'nin ölçtüğü şey çalışan şey olmaz.

### ⚖️ YUMUŞAK — yalnız öncelik, güvenlik değil

- **0012 Faz 2 → 0007 Faz 1b, 0012 Faz 3, 0013 Faz 2.** Ölçüm betiği önce ısınma,
  `--cihaz` ve tekrar kazanmalı; yoksa ilk kaydın süresi soğuk başlangıcı içerir ve
  GPU ölçülemez. Kayıt seti üç plan için ortaktır — kullanıcı bir kez kaydeder.
- **0006 Faz 1–3 → 0007 Faz 1b.** Tuş ve mikrofon gecikmesi düşmeden alınan
  ölçüm, kısa kayıtları olduğundan kısa gösterir ve 0007'nin asgari süre
  kararını yanıltır. Ters sıra zararsızdır ama ölçüm tekrarlanmalıdır.

- **0002 → 0004 Faz 1.** İkisi de ses yolunun log/kaynak davranışına dokunur;
  önce 0002 yapılırsa 0004'ün ses testleri tek seferde yazılır. Ters sıra
  **zararsızdır**. ✅ Karşılandı (2026-10-01): ikisi de bu sırayla kapandı.
- **0003 → 0005.** 0005 ≥ 100 ms çıkarsa `TrayApp` ile `AudioWorker`
  arasındaki çağrılar sinyale döner; 0003'ün `TrayApp` testleri o zaman
  zaten yerinde olur. ✅ 0003 kapandı (2026-10-01).

---

## Tavsiye edilen sıra (öneri, emir değil)

```
0001 ✅ ──► 0002 ✅ ──► 0003 ✅ ──► 0004 ✅   (2026-10-01'de kapandı)
0006 Faz 1–3 ✅ ──► 0007 Faz 1a ✅ ──► (kullanıcı ölçümleri) ──► 0006 Faz 4 kararı, 0007 Faz 2
0005  (kullanıcı ölçümü gelince, bağımsız)
0008 Faz 1 ✅ ──► (kullanıcının Windows log'u)
0009 Faz 1 ✅ ──► (kullanıcı kararı) ──► Faz 2 dağıtım, Faz 3 ayar ekranı ──► Faz 4 (0007 Faz 1b'nin kayıtlarıyla)
0012 Faz 1–2 ✅ ──► (kullanıcı: ortak kayıt seti, 0007 Faz 1b + 0012 Faz 3 + 0013 Faz 2) ──► 0012 Faz 4 ──► 0014 Faz 0 kararı
0013 (kaynak kararı) ──► Faz 1 ──► Faz 2 ölçümü
```

⚖️ **2026-10-06 eki:** 0012 Faz 1–2 ölçüm beklemeden yapılabilir ve sonraki bütün
hız kararlarının (0006 Faz 4, 0007 Faz 2, 0009, 0013, 0014) ölçüm aracıdır → hız
işlerinde önce o.

⚖️ **Gerekçe:** 0006 Faz 1–3 ölçüm beklemeden yapılabilir ve kısa kayıtları
uzatır; 0007'nin ölçümü bu yüzden 0006'dan **sonra** alınırsa "0,5 sn altı"
katmanı adil tartılır.

🛑 **Bu sıra bir yasak değildir.** Kullanıcı başka bir sırayı söylerse o geçerlidir.

---

## Plan yazma kuralları

Yeni plan yazacak ajan için. Örnekler: yukarıdaki beş plan.

**Dosya adı:** `NNNN-kisa-turkce-konu.md` — dört haneli, sıradaki numara,
küçük harf, Türkçe karakter yok.

**Başlık bloğu (her planda):**

```markdown
# Plan NNNN — Konu

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏳ **BAŞLANMADI** | ⏸️ **VERİ BEKLİYOR** | ✅ **KAPANDI** YYYY-AA-GG
**Kullanıcı verisi değişikliği:** YOK | VAR — açık onay; gerekiyorsa taşıma kodu (CONTEXT.md → Mimari Kurallar #8)
**Öncelik:** 🔴 Yüksek | 🟠 Orta-yüksek | 🟡 Orta | 🟢 Düşük — tek cümle gerekçe
**Tarih:** YYYY-AA-GG
**İlgili belgeler:** tarama belgesi §, ADR, CONTEXT.md bölümü
```

**Bölümler (sırayla; gereksizse atla):**

| Bölüm | İçerik |
|---|---|
| Neden bu plan | Kusur, `dosya:satır` ile. Senaryo varsa **nasıl doğrulandığını** yaz ("kod okumasıyla, çalıştırılarak denenmedi") |
| Devralma notu | Depodan doğrulama komutları: "Beklenen (iş BAŞLAMADIYSA) / (BİTTİYSE)". Ortam notları |
| Kararlar | Tablo: konu · karar · gerekçe. Domain kararı gerekiyorsa **"kullanıcıya sor"** yaz, tahmin etme |
| Fazlar | `- [ ]` kutuları. Her faz kendi testiyle |
| Bilinçli olarak YAPILMAYACAKLAR | Kapsam dışı ve neden |
| Test stratejisi | Test adları; **kırmızı kanıtı** zorunlu (değişiklik geri alınınca test kırmızıya dönmeli) |
| Riskler | Tablo: risk · şiddet · azaltma |
| Efor | Kaba süre |
| Yürütme günlüğü | Tarihli satırlar: ne yapıldı, plandan sapmalar, test sonucu |

**Simgeler:** 🛑 kural/yasak · ⚠️ dikkat · ⚖️ gerekçe · ✅ tamam · ⏳ başlanmadı · ⏸️ bekliyor.

**Plan kapanınca:** "Durum" satırı `✅ KAPANDI YYYY-AA-GG` olur, "Yürütme
günlüğü"ne kapanış girdisi yazılır, bu README'deki tablo güncellenir. Karar
kalıcı bir mimari kural doğuruyorsa ADR yazılır ve CONTEXT.md'ye işlenir.

**Bulgular nereden gelir:** Tarama/inceleme belgelerinden
(`docs/<tür>-incelemesi-YYYY-AA-GG.md`, ör. `docs/kod-incelemesi-2026-10-01.md`,
`docs/hiz-dogruluk-incelemesi-2026-10-01.md`). O
belgeler kanıt kaynağıdır, plan değildir. 🛑 Yeni bir taramaya başlamadan
önce mevcut tarama belgelerini oku — bilinen bulguyu yeniden keşfetme.

---

## Kapalı planlar

Kapanan planlar silinmez; bir kararın neden öyle alındığının tarihsel kaydıdır.

| Plan | Konu | Kapanış |
|---|---|---|
| [0001](0001-bozuk-model-sonrasi-yukleme-kilidi.md) | Bozuk model sonrası model yükleme kilidi | 2026-10-01 |
| [0002](0002-kayit-sonunda-stream-kapanmiyor.md) | Kayıt sonunda mikrofon stream'i kapanmıyor | 2026-10-01 |
| [0003](0003-durum-satirinda-kalan-iki-kacak.md) | Durum satırında kalan iki kaçak | 2026-10-01 |
| [0004](0004-log-hattini-tamamlama.md) | Log hattını tamamlama (ADR-0004'ün kalan yarısı) | 2026-10-01 |
