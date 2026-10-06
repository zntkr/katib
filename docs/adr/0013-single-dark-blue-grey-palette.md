# ADR-0013: Tek Renk Şeması — Koyu Mavimsi Gri; Açık Tema Yok

## Durum
Kabul edildi (2026-10-04). ADR-0012'nin "Uygulama" sekmesindeki tema seçimini kaldırır.

## Bağlam
`ui/theme.py` iki palet taşıyordu (koyu ve açık, ikisi de Gruvbox'ın kahverengi-sepya
tonları, 33'er anahtar) ve bir `theme` ayarı vardı (`system` / `dark` / `light`).

- Proje sahibi sepya tonlarını, özellikle arka planları beğenmedi; koyu mavimsi gri istedi ve
  açık temanın kalkmasına karar verdi (2026-10-04).
- İki palet her renk kararını ikiye katlıyordu: her ekran görüntüsü, her kontrast denetimi iki
  kez yapılıyordu. 33 anahtarın 8'ini hiçbir kod okumuyordu; stil dosyasında silinmiş
  bileşenlerin (sayı kutuları, onay kutuları) kuralları duruyordu.
- Tema değişince pencereyi yeniden kuran, Windows'un renk tercihini dinleyen ve ok
  simgelerini tema başına ayrı dosyaya yazan kod yalnız bu seçim için vardı.
- Arayüzün büyük kısmı zaten koyu zemin varsayıyordu: pill ekranın üstünde yüzen koyu bir
  şekil, pencerelerin başlık çubuğu koyuya çevriliyor.

## Karar
- **Tek palet:** `ui/theme.py::PALETTE` (21 renk). Arka planlar ve çerçeveler koyu mavimsi
  gri (`#0e1116` … `#3d485b`), metin grileri aynı tona çekik, vurgu rengi mavi
  (`CLR_ACCENT`), durum renkleri yeşil / kırmızı / turuncu / camgöbeği.
- **Açık tema ve tema ayarı yoktur.** `theme` anahtarı `DEFAULTS`'tan çıkarıldı; ayar
  penceresinde tema seçimi, `theme_changed` sinyali ve Windows'un açık/koyu tercihini izleyen
  bağlantı kaldırıldı. `ThemeManager.apply_theme(app)` açılışta bir kez çağrılır.
- **Palet tek kaynaktır ve testle korunur** (`tests/test_theme.py`, `tests/test_ssot.py`):
  - kodun istediği her renk palette tanımlıdır, palette kullanılmayan renk yoktur;
  - arka planlar koyudur ve mavi kanalı kırmızıdan büyüktür (kahverengiye dönüşü yakalar);
  - metin ve durum renkleri üç zeminde de en az 4,5:1 kontrast verir (ikincil metin,
    kullanıldığı iki zeminde);
  - `ui/` altında ve stil dosyasında palet dışı renk sabiti yoktur.

## Reddedilen Alternatifler
- **Açık temayı da mavi-griye çevirip korumak:** Proje sahibi istemedi; bakım yükü ikiye
  katlanmaya devam ederdi.
- **`theme` ayarını tutup yok saymak:** Ekranda hiçbir şey değiştirmeyen bir seçim ya da
  kodda okunmayan bir ayar bırakırdı.

## Sonuçlar
- **Kullanıcı verisi:** eski sürümden kalan `settings.json` içindeki `"theme"` satırı
  silinmez ve okunmaz (bilinmeyen anahtarlar korunur — `tests/test_config.py`). Açık temayı
  seçmiş kullanıcı güncellemeden sonra koyu arayüz görür. Bu değişiklik proje sahibinin
  isteğiyle yapıldı (CONTEXT.md kural 8).
- Windows açık temadayken de Katib koyu görünür.
- Yeni bir renk gerekiyorsa `PALETTE`'e eklenir; testler onun kullanıldığını ve okunaklı
  olduğunu denetler. Bileşenlerde renk sabiti yazılmaz.
- Çeviri dosyalarından dört metin silindi (`settings.theme_label`, `theme_system`,
  `theme_dark`, `theme_light`).
- Stil dosyasındaki ölü kurallar (sayı kutusu, onay kutusu, düz metin kutusu) ve tema başına
  simge önbelleği kaldırıldı.
