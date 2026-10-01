# Plan 0003 — Durum Satırında Kalan İki Kaçak

> **Bu yaşayan bir belgedir.** Her faz bitince kutusunu işaretle ve "Yürütme
> günlüğü"ne bir satır ekle.
> Göreve yeni başlayan ajan: önce [Devralma notu](#devralma-notu) bölümünü oku.

**Durum:** ⏳ **BAŞLANMADI** — 0/2 faz
**Ayar dosyası (`settings.json`) değişikliği:** YOK
**Öncelik:** 🟡 Orta — yanlış durum bilgisi, veri kaybı yok.
**Tarih:** 2026-10-01
**İlgili belgeler:** `docs/kod-incelemesi-2026-10-01.md` §3–4, CONTEXT.md →
Geliştirici Notları ("Dashboard durum satırını ve tray ipucunu yalnızca
`TrayApp._resolve_status()` yazar")

---

## Neden bu plan

`e2ac44d` durum satırını tek sahibe (`TrayApp._resolve_status()`) bağladı.
İnceleme iki kaçak buldu; ikisi de aynı modülde, aynı kuralın ihlali.

1. **Kayıt, devam eden indirmenin bildirimini siliyor.** `ui/tray_app.py:175`
   — `set_recording(True)` `_download_notice`'i koşulsuz siler. İndirme
   sürerken dikte yapılırsa, kayıt bitince durum satırı "Hazır" gösterir;
   indirme bitene kadar "İndiriliyor…" geri gelmez.
2. **Dil değişince tepsi ipucu "Hazır"a dönüyor.** `apply_language()`
   (satır 78) tepsiyi `_build_tray()` ile yeniden kurar; o da satır 86'da
   ipucunu sabit `STATE_READY` yazar, simgeyi boşta simgesine çevirir ve
   `_resolve_status()` çağrılmaz. Mikrofon yokken ya da kayıt sırasında dil
   değişirse tepsi yanlış durum gösterir.

---

## Devralma notu

**Nerede kaldık? — depodan doğrula**

```bash
# Kaçak 2 (iş BAŞLAMADIYSA): _build_tray sabit "Ready" ipucu yazıyor → 1 satır
sed -n '/def _build_tray/,/def _build_no_tray/p' ui/tray_app.py | grep -c "STATE_READY"
# Kaçak 1 (iş BİTTİYSE): indirme durumu TrayApp'e bağlı
grep -n "download_state_changed.connect(tray" main.py
```

**Ortam**
- Testler: `python -m pytest -q`; referans Windows CI.
- Durum testleri: `tests/test_tray_app.py::TestStatusOwnership` (yardımcı
  `_shows(tray, key)` hem durum satırına hem ipucuna bakar).

---

## Kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| İndirmenin sürdüğünü TrayApp nereden bilir | `downloader_worker.download_state_changed` → yeni `TrayApp.on_download_state(active)` | Sinyal zaten var; bugün yalnız dashboard'a bağlı (`main.py:293`) |
| Kayıt neyi siler | Yalnız **bitmiş** sonucu (hata, disk dolu); indirme sürüyorsa bildirim kalır | Eski davranışta da hata bildirimi kayıttan sonra kayboluyordu |
| `_build_tray` ipucu | Sabit ipucu kalkar; `apply_language` sonunda `_resolve_status()` | Tek yazar kuralı |

---

## Faz 1 — İndirme sürerken bildirim kalır

- [ ] `TrayApp.on_download_state(active: bool)`: `_downloading` olgusunu tutar.
- [ ] `set_recording(True)`: `_download_notice`'i yalnız `not self._downloading`
      ise siler.
- [ ] `main.py`: `downloader_worker.download_state_changed.connect(tray.on_download_state)`
      (mevcut dashboard bağlantısı kalır — yükleme çubuğu için).
- [ ] Test: `test_recording_keeps_notice_while_download_runs` ve
      `test_recording_clears_finished_download_error`.

## Faz 2 — Dil değişince doğru tepsi durumu

- [ ] `_build_tray()` içindeki `setToolTip(...STATE_READY...)` kalkar.
- [ ] `apply_language()` sonunda `self._resolve_status()`.
- [ ] Test: `test_language_change_keeps_no_mic_tooltip` (mikrofon yok → dil
      değişir → ipucu "Mikrofon Yok") ve `test_language_change_while_recording_keeps_rec_icon`.

⚠️ **Kırmızı kanıtı:** her yeni test bugünkü kodla kırmızı olmalı.

---

## Bilinçli olarak YAPILMAYACAKLAR

- **İndirme ilerleme yüzdesi.** `snapshot_download` ilerleme vermiyor; ayrı iş.
- **Durum önceliğini değiştirmek.** Sıra (kayıt > işleme > indirme > mikrofon >
  model) korunur.

## Riskler

| Risk | Şiddet | Azaltma |
|---|---|---|
| `download_state_changed` ile `status_changed` sırası | Düşük | Downloader önce durumu, sonra `download_state_changed(False)`'u yayıyor; `_downloading` yalnız kaydın silme kararını etkiler |

## Efor

Faz 1: 30 dk · Faz 2: 20 dk → **~50 dk**

---

## Yürütme günlüğü

*(henüz yok)*
