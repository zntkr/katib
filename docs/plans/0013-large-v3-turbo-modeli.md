# Plan 0013 — `large-v3-turbo` Modeli

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏸️ **KARAR BEKLİYOR** — model kaynağı ve listedeki yeri proje sahibinin kararı.
**Kullanıcı verisi değişikliği:** YOK — yeni bir model girdisi yeni bir klasör
(`Models\faster-whisper-large-v3-turbo`) ekler; mevcut klasör adları, ayar anahtarları
ve varsayılan model (`small`) değişmez.
**Öncelik:** 🟠 Orta-yüksek — "macOS diktesine yakın kalite" hedefinin (ADR-0010) GPU'daki
en doğal adayı; uzun diktelerde (proje sahibinde çoğunluk 15 sn+) `large-v3`'ten çok
daha hızlı olması beklenir.
**Tarih:** 2026-10-06
**İlgili belgeler:** `docs/hiz-incelemesi-2026-10-06.md` §8; ADR-0010; plan 0009 (GPU
dağıtımı); plan 0012 (ölçüm betiği)
**Bağımlılık:** ⚖️ Yumuşak: plan 0012 Faz 2 (betik `--cihaz cuda` ve tekrar) önce
gelirse Faz 2'nin ölçümü tek seferde alınır. **Yeni paket YOK.**

---

## Neden bu plan

`core/settings.py::WHISPER_MODELS` beş model sunuyor: tiny, base, small, medium,
large-v3. `large-v3` en doğrusu ama 32 katmanlı çözümleyicisiyle en yavaşı.
`large-v3-turbo` aynı kodlayıcıyı ve **4 katmanlı** bir çözümleyiciyi taşır,
çok dillidir (Türkçe dahil). Çözümleyici süresi metin uzunluğuyla büyüdüğü için
uzun diktelerde fark büyüktür. Kodlayıcı aynı olduğundan CPU'da kısa kayıtta
kazanç sınırlıdır → asıl hedef GPU'lu kullanıcı.

faster-whisper 1.2.1 `utils.py::_MODELS`, `"large-v3-turbo"` ve `"turbo"` adlarını
`mobiuslabsgmbh/faster-whisper-large-v3-turbo`'ya eşliyor. Systran bu modeli
yayımlamıyor.

---

## Devralma notu

```bash
# Faz 1 BAŞLAMADIYSA: çıktı boş; BİTTİYSE: girdi var
grep -n "large-v3-turbo" core/settings.py
# Model listesinin geçtiği diğer yerler (Faz 1'de birlikte güncellenir)
grep -n "large-v3" ui/help_window.py docs/guides/enterprise_deployment.md README.md
```

**Ortam**
- `ModelDownloaderWorker` `snapshot_download(repo_id=...)` kullanır; klasör adı
  `repo_id`'nin son parçasıdır → `faster-whisper-large-v3-turbo`.
- `ModelProvider.get_active_model_path()` seçili model geçersizse `WHISPER_MODELS`
  sırasındaki **ilk kurulu** modeli seçer → yeni girdinin sırası bu davranışı etkiler.
- Ayar penceresi etiketi `f"{key.capitalize()} ({size})"` ile üretilir
  (`ui/settings_window.py::_build_model_column`).

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Kaynak depo | **Kullanıcıya sor.** Öneri: `mobiuslabsgmbh/faster-whisper-large-v3-turbo` | faster-whisper'ın kendi eşlemesi bu depo; ama Systran dışı bir yayıncıya güven bir karar (ADR-0002: indirme tek ağ erişimi) |
| Sürüm sabitleme | `snapshot_download(revision=<commit>)` ile belirli bir commit **önerilir** | Üçüncü taraf depo sonradan değişirse kullanıcılar farklı ağırlık indirmesin; bugün diğer modeller sabitlenmiyor → kullanıcıya sor |
| Listedeki yer | `large-v3`'ten **önce** (ya da sonra) — **kullanıcıya sor** | Sıra, bozuk seçimde hangi kurulu modele düşüleceğini belirler |
| Varsayılan model | `small` kalır | Varsayılan değişikliği kural #8 kapsamında; turbo CPU'da kısa kayıtta yavaş |
| Etiket/açıklama | "Turbo (~1.6 GB)"; yardım penceresinde "GPU önerilir" | Kullanıcı CPU'da seçip yavaşlığa şaşırmasın |

---

## Faz 1 — Modeli listeye ekle

- [ ] `WHISPER_MODELS`'a girdi (`repo_id`, `size`, `desc`, `req_bytes`); `req_bytes`
      indirilen klasörün gerçek boyutuyla (indirme sonrası ölçülür) + pay.
- [ ] Karar verildiyse `revision` sabitlemesi (`ModelDownloaderWorker`).
- [ ] `ui/help_window.py` model tablosu, `docs/guides/enterprise_deployment.md` klasör
      tablosu, 11 README'nin model tablosu, gerekirse çeviri anahtarları.
- [ ] Testler: `tests/test_paths.py` ve `tests/test_model_downloader_worker.py`'nin
      model listesi testleri yeni girdiyi kapsar; klasör adı `faster-whisper-large-v3-turbo`;
      `ModelProvider` sıra davranışı (seçili model geçersiz → beklenen model).

## Faz 2 — Ölçüm (kullanıcı)

- [ ] `olcum.py --model <turbo klasörü> --cihaz cuda` ve `--cihaz cpu`; `large-v3` ve
      `medium` ile aynı kayıtlar, aynı çözümleme ayarları. Süre (kırılımlı) ve WER günlüğe.
- [ ] Sonuca göre yardım penceresi metni ("GPU önerilir" / "CPU'da da uygun").

---

## Bilinçli olarak YAPILMAYACAKLAR

- **`distil-*` modelleri.** Ağırlıkla İngilizce; Türkçe hedefi karşılamaz.
- **Modeli kurulum paketine gömmek.** ~1,6 GB; indirme modeli değişmez (ADR-0002).
- **Cihaza göre otomatik model seçimi.** Kullanıcının seçimini uygulama değiştirmez.

## Test stratejisi

Faz 1 testleri yukarıda. ⚠️ **Kırmızı kanıtı:** "listede turbo var / klasör adı" testi
girdi yokken kırmızı. Hız iddiası yalnız Faz 2 ölçümüyle.

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| Üçüncü taraf depo değişir ya da kaldırılır | Orta | `revision` sabitleme; indirme hatası bugünkü hata yolundan geçer |
| Turbo Türkçede `large-v3`'ten belirgin kötü | Orta | Faz 2 WER ölçümü; kötüyse açıklama metni dürüstçe yazar |
| CPU kullanıcısı turbo'yu seçip yavaşlık yaşar | Düşük | Etiket ve yardım metni |

## Efor

Faz 1: 1–1,5 sa · Faz 2: kullanıcı

---

## Yürütme günlüğü

### 2026-10-06 — Plan açıldı

`docs/hiz-incelemesi-2026-10-06.md` §8'den. Kod değişikliği yok.
