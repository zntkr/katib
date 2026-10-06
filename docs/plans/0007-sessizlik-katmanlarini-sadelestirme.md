# Plan 0007 — Sessizlik Katmanlarını Sadeleştirme (önce ölç)

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **VERİ BEKLİYOR** — Faz 1a bitti (2026-10-01); Faz 1b kullanıcının
kayıtlarını bekler.
**Kullanıcı verisi değişikliği:** YOK (`settings.json` ve veri klasörleri değişmiyor)
**Öncelik:** 🟠 Orta-yüksek — sessiz konuşanın ve kısa yanıtların ("Evet.",
"Tamam.") kaydı sessizce kaybolabiliyor.
**Tarih:** 2026-10-01
**İlgili belgeler:** `docs/hiz-dogruluk-incelemesi-2026-10-01.md` §1 (filtre
ödünleşimi) ve §3, CONTEXT.md → "Binary Armor", ADR-0004 (gizlilik)
**Bağımlılık:** Yok. **Yeni paket YOK** (kelime hata oranı elle, ~15 satır).

---

## Neden bu plan

Bir kayıt yazıya dökülmeden önce **dört** ayrı yerde elenebiliyor:

| # | Katman | Yer | Eler |
|---|---|---|---|
| 1 | Asgari süre | `workers/audio_worker.py` `MIN_RECORDING_DURATION = 0.5` | 0,5 sn'den kısa her kayıt |
| 2 | Kendi seviye analizimiz | `core/audio_analysis.is_silent()` | konuşma tepesi < -55 dB, ya da 0,3 sn'den az "sesli" bölüm, ya da düz ve kısık sinyal |
| 3 | Whisper | `transcription_worker._transcribe`: `vad_filter=True` (eşik 0.4, en kısa konuşma 200 ms), `no_speech_threshold=0.6` | Whisper'ın "konuşma yok" saydığı bölümler |
| 4 | Uydurma filtresi | `core/transcription_filter.py` | kısa kayıtta yalnız kalıp ifadeler |

Sorunlar (kod okuması, **ölçülmedi**):
- "Evet." / "Tamam." hızlı söylenince ve tuşa geç basılınca (plan 0006) 0,5 sn
  altında kalabilir → katman 1 atar, kullanıcı "Kayıt çok kısa" görür.
- Kısık mikrofon ya da fısıltı → katman 2 atar ("Ses seviyesi çok düşük").
- Katman 2 ile 3 aynı işi iki kez yapıyor; CONTEXT.md'deki **Binary Armor**
  ilkesi ("tam 0.0 hata, 0.0'dan büyük her sinyal — fısıltı dahil — işlenir")
  ile katman 2 çelişiyor.
- Katman 4'ün bilinçli ödünleşimi: kısa kayıtta **yalnız** "Teşekkürler."
  dikte edilirse atılır.

⚖️ Katmanların **neden** eklendiği belli: Whisper sessizliğe uydurma metin
yazar. Ama hangisinin gerçek kaydı ne sıklıkla attığı ölçülmedi. Bu plan
tahminle eşik oynatmaz; önce ölçer.

### Hangisi daha kararlı: Silero VAD mi, kendi seviye analizimiz mi? *(2026-10-06)*

Proje sahibinin sorusu; ayrıntı `docs/hiz-incelemesi-2026-10-06.md` §11 (kaynak + kod okuması).

| | Katman 2 — `is_silent` | Katman 3 — `vad_filter` |
|---|---|---|
| Yöntem | Enerji (RMS) eşiği, sabit -55 dB | Silero VAD v6 (sinir ağı, faster-whisper'ın içinde) |
| Ayırt ettiği | Yalnız "ne kadar yüksek" | "Konuşma mı": fan, klavye, müzik konuşmadan ayrılır |
| Karar | Kaydın tamamına evet/hayır | Konuşma bölümlerini bulur, aradaki sessizliği atar |
| Zayıf yeri | Kısık mikrofon, fısıltı; yüksek sesli gürültüyü geçirir | Yumuşak başlayan kelime (`speech_pad_ms=400` dolgu) |

**Değerlendirme:** Silero daha kararlıdır; içeriğe bakar, mikrofon kazancına bağlı
değildir. Katman 2 yalnız kısa basışlarda ve kısık mikrofonda karar verir — yani
tam da gerçek kaydı kaybetme riskinin olduğu yerde. **Uzun diktelerde** (proje
sahibinde çoğunluk 15 sn+) katman 2 neredeyse hiç devreye girmez, Silero'nun değeri
ise artar: düşünme duraklamaları Whisper'ın en çok uydurduğu yerdir ve 30 sn sınırını
aşan sesi kısaltır. Bu, aşağıdaki hedef yapıyı (katman 2 → yalnız tam sıfır; sessizlik
kararı Silero'da) destekler; karar yine Faz 1b ölçümüyle verilir.

---

## Devralma notu

**Nerede kaldık? — depodan doğrula**

```bash
# Faz 1a BİTTİYSE: ölçüm betiği var
ls scripts/olcum.py
# Faz 1b BİTTİYSE: ölçüm sonucu bu planın Yürütme günlüğünde tablo olarak duruyor
# Faz 2 BAŞLAMADIYSA: üç sabit de yerinde
grep -n "MIN_RECORDING_DURATION *=\|silence_db: float = -55\|vad_filter *= True" workers/audio_worker.py core/audio_analysis.py workers/transcription_worker.py
```

**Ortam**
- Testler: `python -m pytest -q`; referans Windows CI.
- 🛑 **Ölçüm kayıtları kullanıcının sesidir — kişisel veri.** Depoya ve kurulum
  paketine GİREMEZ: `olcum/` klasörü `.gitignore`'a eklenir (Faz 1a), betik
  kayıtları oradan okur. Dikte metinleri log'a yazılmaz (ADR-0004).
- Ölçüm gerçek model ister → yalnız kullanıcının makinesinde koşar.

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Eşik değiştirmeden önce | Ölçüm seti + betik (Faz 1) | "Daha doğru" iddiası ancak bir ölçüte göre tartılabilir |
| Ölçüm seti | Kullanıcının 20–30 kısa kaydı: kısa yanıtlar (Evet/Tamam/Hayır), normal cümleler, kısık/fısıltı, gürültülü ortam, **konuşmasız** basışlar (yanlışlıkla dokunuş, ortam sesi), yalnız "Teşekkürler."; ayrıca **duraklamalı 15 sn+ dikteler** (2026-10-06; plan 0012 ile ortak set) | Hem kaybolan gerçek kaydı (yanlış negatif) hem geçen uydurmayı (yanlış pozitif) görmek için |
| Ölçülenler | Her kayıt için: hangi katmanda elendi / geçti, Whisper metni, doğru metne göre kelime hata oranı, Whisper süresi | Katman bazında karar |
| Hedef yapı (ölçüme göre kesinleşir) | Katman 1: yalnız **yanlışlıkla dokunuş** (~0,2 sn altı). Katman 2: yalnız **tam sıfır** (Binary Armor, susturulmuş mikrofon). Katman 3: ölçüme göre `vad_filter` kalır ya da gider. Katman 4: kalır | Binary Armor ilkesine dönüş; sessizlik kararını Whisper'a bırakmak |
| Başarı ölçütü | Konuşmalı kayıtlarda elenen = 0; konuşmasız kayıtlarda yapıştırılan uydurma metin = 0 (ya da bugünkü değerden kötü değil) | İki hata türü birlikte tartılır |

---

## Faz 1 — Ölçüm altyapısı

**1a — betik (ajan):**
- [x] `scripts/olcum.py`: `olcum/*.wav` + aynı adlı `.txt` (doğru metin; konuşmasız
      kayıt için boş dosya). Her kaydı uygulamanın **gerçek** fonksiyonlarından
      geçirir: süre kontrolü, `analyse_vad`/`is_silent`, aynı parametrelerle
      `WhisperModel.transcribe`, `TranscriptionFilter.clean`. Çıktı: katman
      bazında tablo + toplam kelime hata oranı + ortalama Whisper süresi.
- [x] Parametreleri komut satırından değiştirilebilir yapar (`--min-sure`,
      `--silence-db`, `--vad/--no-vad`) — Faz 2'nin karşılaştırması için.
- [x] `.gitignore`: `olcum/`.
- [x] Test: kelime hata oranı fonksiyonu (bilinen örnekler) ve "katman 1/2'de
      elenen kayıt Whisper'a gitmez" akışı, Whisper sahte nesneyle.

**1b — kayıtlar (kullanıcı):**
- [ ] Kullanıcı kayıtları `olcum/`'a koyar ve betiği çalıştırır; tablo bu planın
      "Yürütme günlüğü"ne yapıştırılır (metinler değil, yalnız sayılar ve
      elenme nedenleri — gizlilik).

## Faz 2 — Katmanları ölçüme göre sadeleştir

- [ ] Ölçüm tablosuna göre her katman için tek tek karar; her kararın gerekçesi
      ölçüm satırına atıfla bu planın günlüğüne yazılır.
- [ ] Beklenen değişiklikler: `MIN_RECORDING_DURATION` düşer; `is_silent`
      dB/sesli-süre kuralları kalkar ya da gevşer; `vad_filter` ölçüme göre.
- [ ] Testler: mevcut `tests/test_audio_analysis.py` ve `tests/test_audio_worker.py`
      beklentileri yeni kurallara çevrilir; yeni: "0,3 sn'lik kısa konuşma
      Whisper'a gider", "tam sıfır sinyal gitmez".
- [ ] Ölçüm betiği yeni ayarlarla yeniden çalıştırılır; önce/sonra tablosu günlüğe.

## Faz 3 — Belgeler ve artıklar

- [ ] CONTEXT.md "Binary Armor" tanımı yeni davranışla eşitlenir.
- [ ] Kullanılmayan OSD metinleri (ör. `osd.audio_too_quiet`,
      `osd.recording_too_short`) 11 dil dosyasından kalkar.
- [ ] `docs/hiz-dogruluk-incelemesi-2026-10-01.md` §3 → ✅ DÜZELTİLDİ.

---

## Bilinçli olarak YAPILMAYACAKLAR

- **Ölçümsüz eşik değişikliği.**
- **Yeni VAD modeli / kütüphanesi.** Whisper'ın kendi VAD'ı zaten var.
- **Kullanıcıya eşik ayarı.** Kullanıcı ayar kurcalamamalı; varsayılan doğru olmalı.
- **Ölçüm kayıtlarını depoya koymak** (gizlilik).

## Test stratejisi

Faz 1'de betiğin saf parçaları (kelime hata oranı, katman akışı) birim testli;
Faz 2'de davranış testleri yeni kurallara çevrilir. ⚠️ **Kırmızı kanıtı:**
"kısa konuşma Whisper'a gider" testi bugünkü kodla kırmızı olmalı.

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| Katmanlar gevşeyince sessiz basışlarda uydurma metin yapıştırılır | Yüksek | Başarı ölçütü konuşmasız kayıtları ayrıca sayar; katman 4 kalır |
| Ölçüm seti küçük → yanlış genelleme | Orta | Kayıt türleri bilinçli seçilir (Kararlar); şüphede mevcut katman korunur |
| Kayıtların yanlışlıkla depoya girmesi | Yüksek | `.gitignore` Faz 1a'nın ilk maddesi |

## Efor

Faz 1a: 2 sa · Faz 1b: kullanıcı · Faz 2: 1–2 sa · Faz 3: 30 dk

---

## Yürütme günlüğü

### 2026-10-01 — Faz 1a uygulandı

`scripts/olcum.py` yazıldı. Kayıtları uygulamanın **gerçek** fonksiyonlarından
geçiriyor: `MIN_RECORDING_DURATION`, `analyse_vad`/`is_silent`, Whisper,
`TranscriptionFilter.clean`. Whisper ayarları için `workers/transcription_worker.py`'de
`TRANSCRIBE_OPTIONS` sabiti çıkarıldı; worker ve betik aynı sözlüğü kullanıyor,
yani ölçülen şey kullanıcının çalıştırdığı şey. Rapor dikte metnini varsayılan
olarak göstermiyor (`--metin` ile gösteriyor); `olcum/` `.gitignore`'da
(`git check-ignore` ile doğrulandı).

⚠️ Plandan sapma: katman 2'nin "en az 0,3 sn sesli bölüm" kuralı `--silence-db`
ile kapatılamadığı için `--no-seviye` eklendi (katman 2'yi tamamen kapatır).
Seviye analizi uygulamadaki gibi 1024 örneklik bloklarla yapılıyor; uygulamada
blok cihaz hızında alındığından (ör. 48 kHz'te 21 ms) eşikler birebir aynı
olmayabilir — plan 0006 Faz 2 sonrası çoğu cihaz 16 kHz'te açılacağı için fark
küçülür.

**Testler:** `tests/test_olcum.py` (15): kelime hata oranı (büyük/küçük harf ve
noktalama sayılmaz, Türkçe harf farkı sayılır), katman akışı (elenen kayıt
Whisper'a gitmez; Whisper uygulamanın ayarlarıyla çağrılır; katmanlar
kapatılabilir), WAV okuma (48 kHz stereo → 16 kHz mono), rapor sayıları ve
metin gizliliği. Kırmızı kanıtı: betik yokken toplama hatası.

**Kullanıcı için (Faz 1b):**

```powershell
# proje kökünde; olcum\ klasörüne a.wav + a.txt çiftleri
python scripts\olcum.py                                     # bugünkü ayarlar
python scripts\olcum.py --min-sure 0.2 --no-seviye --no-vad  # katmanlar kapalı
```

İki raporu da (metinsiz hâlleriyle) buraya yapıştırın.

### 2026-10-06 — Silero / seviye analizi karşılaştırması eklendi

Proje sahibinin "VAD mı kararlı, kendi sistemimiz mi?" sorusu "Neden bu plan"
altına tabloyla yazıldı (`docs/hiz-incelemesi-2026-10-06.md` §11). Ölçüm setine
duraklamalı 15 sn+ dikteler eklendi (diktelerin çoğu bu uzunlukta); set plan 0012
ile ortak. Kod değişikliği yok.
