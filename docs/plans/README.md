# Planlar — açık işler haritası

> Bu dosya **yalnız yön tarifidir**. Gerçek bilgi planların kendisindedir;
> her plan kendi kendine yeten bir devir belgesidir. Bir sayıya ya da karara
> ihtiyacın varsa planı aç, buradan alıntılama.

**Son güncelleme:** 2026-10-01 · **7 plan, 4 kapalı, 3 açık.** (0006–0007 hız/doğruluk incelemesinden açıldı.)

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
| [0006](0006-kayit-baslangici-gecikmesi.md) | Kayıt başlangıcı: gecikme ve kesilen ilk hece | 🟠 Orta-yüksek | Faz 4: kullanıcı kararı |
| [0007](0007-sessizlik-katmanlarini-sadelestirme.md) | Sessizlik katmanlarını sadeleştirme (önce ölç) | 🟠 Orta-yüksek | Faz 1b: kullanıcının kayıtları |
| [0005](0005-ses-islerinin-ui-thread-olcumu.md) | Ses işlerinin UI thread'de çalışması | ⏸️ Veri bekliyor | Kullanıcının Windows ölçümü |

0001–0004 2026-10-01'de kapandı (aşağıda "Kapalı planlar"). 0006–0007
`docs/hiz-dogruluk-incelemesi-2026-10-01.md`'nin bulgularıdır.

---

## İki tür bağımlılık — karıştırma

### 🛑 SERT — bozarsan bir şey kırılır

*Şu an yok.*

### ⚖️ YUMUŞAK — yalnız öncelik, güvenlik değil

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
0006 Faz 1–3 ──► 0007 Faz 1a ──► (kullanıcı ölçümleri) ──► 0006 Faz 4 kararı, 0007 Faz 2
0005  (kullanıcı ölçümü gelince, bağımsız)
```

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
