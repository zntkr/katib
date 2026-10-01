# Planlar — açık işler haritası

> Bu dosya **yalnız yön tarifidir**. Gerçek bilgi planların kendisindedir;
> her plan kendi kendine yeten bir devir belgesidir. Bir sayıya ya da karara
> ihtiyacın varsa planı aç, buradan alıntılama.

**Son güncelleme:** 2026-10-01 · **5 plan, 0 kapalı, 5 açık.**

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
| [0001](0001-bozuk-model-sonrasi-yukleme-kilidi.md) | Bozuk model sonrası model yükleme kilidi | 🔴 Yüksek | — |
| [0002](0002-kayit-sonunda-stream-kapanmiyor.md) | Kayıt sonunda mikrofon stream'i kapanmıyor | 🟠 Orta-yüksek | — |
| [0003](0003-durum-satirinda-kalan-iki-kacak.md) | Durum satırında kalan iki kaçak | 🟡 Orta | — |
| [0004](0004-log-hattini-tamamlama.md) | Log hattını tamamlama (ADR-0004'ün kalan yarısı) | 🟡 Orta | — |
| [0005](0005-ses-islerinin-ui-thread-olcumu.md) | Ses işlerinin UI thread'de çalışması | ⏸️ Veri bekliyor | Kullanıcının Windows ölçümü |

Beşi de `docs/kod-incelemesi-2026-10-01.md`'nin bulgularıdır.

---

## İki tür bağımlılık — karıştırma

### 🛑 SERT — bozarsan bir şey kırılır

*Şu an yok.*

### ⚖️ YUMUŞAK — yalnız öncelik, güvenlik değil

- **0002 → 0004 Faz 1.** İkisi de ses yolunun log/kaynak davranışına dokunur;
  önce 0002 yapılırsa 0004'ün ses testleri tek seferde yazılır. Ters sıra
  **zararsızdır**.
- **0003 → 0005.** 0005 ≥ 100 ms çıkarsa `TrayApp` ile `AudioWorker`
  arasındaki çağrılar sinyale döner; 0003'ün `TrayApp` testleri o zaman
  zaten yerinde olur.

---

## Tavsiye edilen sıra (öneri, emir değil)

```
0001 ──► 0002 ──► 0003 ──► 0004
0005  (kullanıcı ölçümü gelince, bağımsız)
```

⚖️ **Gerekçe:** 0001 kullanıcıyı uygulamayı yeniden başlatmaya zorluyor;
0002 cihazı meşgul bırakabiliyor. 0003 ve 0004 görünürlük ve borç.

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
(`docs/<tür>-YYYY-AA-GG.md`, ör. `docs/kod-incelemesi-2026-10-01.md`). O
belgeler kanıt kaynağıdır, plan değildir. 🛑 Yeni bir taramaya başlamadan
önce mevcut tarama belgelerini oku — bilinen bulguyu yeniden keşfetme.

---

## Kapalı planlar

*Henüz yok.* Kapanan planlar silinmez; bir kararın neden öyle alındığının
tarihsel kaydıdır.
