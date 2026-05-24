[English](README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [日本語](README.ja.md) · [中文](README.zh.md) · [한국어](README.ko.md) · [العربية](README.ar.md)

# Katib

**Windows için çevrimdışı sesli yazı. Tuşa bas, konuş, bırak — metin imlecinde belirir.**

Bulut yok. Abonelik yok. Hiçbir şey bilgisayarından çıkmaz.

---

<p align="center">
  <img src="docs/demo.gif" alt="Hold F9, speak, release — text appears" width="800">
</p>

---

## Nasıl çalışır

1. Herhangi bir metin alanına tıkla — tarayıcı, Word, IDE, sohbet uygulaması, Windows'ta herhangi bir yer
2. Kısayol tuşuna bas (varsayılan **F9**), konuş, bırak
3. Söylediklerin [Whisper](https://github.com/openai/whisper) tarafından yerel olarak metne dönüştürülür ve imlecin bulunduğu yere yazılır

Tek seferlik model indirildikten sonra internet bağlantısı gerekmez.

---

## Özellikler

- **%100 çevrimdışı** — Whisper tamamen CPU üzerinde çalışır; API anahtarı veya hesap gerektirmez
- **Her yerde çalışır** — herhangi bir Windows uygulamasındaki odaklanılabilir metin alanları
- **Bas-konuş** — tut kaydet, bırak dönüştür; yanlışlıkla tetiklenme olmaz
- **Beş model boyutu** — 150 MB ile 3 GB arasında; donanımına göre hız ve doğruluk dengesi
- **18 transkripsiyon dili** — Arapça, Çince, İngilizce, Fransızca, Almanca, Yunanca, Hintçe, Endonezce, İtalyanca, Japonca, Korece, Farsça, Portekizce, Rusça, İspanyolca, Türkçe, Urduca ve otomatik algılama
- **11 arayüz dili** — English, Türkçe, Deutsch, Español, Français, Português, Русский, 日本語, 中文, 한국어, العربية — tam RTL düzen desteği dahil
- **Dil başına AI ipuçları** — her konuşma dili için bağlam belirle; dil değiştiğinde otomatik yüklenir
- **Telemetri yok** — analitik, hata raporlama veya güncelleme sorgusu yok

---

## Kurulum

### Seçenek A — Hazır ikili (önerilen)

Son sürümü [Releases](../../releases) sayfasından indir, zip'i aç, `Katib.exe` dosyasını çalıştır.

> **Windows SmartScreen**, ikili imzasız olduğu için uyarı gösterebilir. **Daha fazla bilgi → Yine de çalıştır** seçeneğine tıkla.

### Seçenek B — Kaynak koddan

Python 3.10 veya üzeri gerektirir

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

---

## Modeller

| Model | Boyut | Hız | Doğruluk | Notlar |
|-------|-------|-----|----------|--------|
| tiny | ~150 MB | Çok hızlı | Düşük | Düşük seviyeli veya eski donanımlar |
| base | ~300 MB | Hızlı | Orta | |
| **small** | **~500 MB** | **Dengeli** | **İyi** | **Başlangıç için önerilen** |
| medium | ~1.5 GB | Yavaş | Yüksek | Teknik içerik, aksanlar |
| large-v3 | ~3 GB | Çok yavaş | Maksimum | Mümkün olan en yüksek doğruluk |

Modeller [Hugging Face (Systran)](https://huggingface.co/Systran) adresinden indirilir ve yerel olarak saklanır. Katib'i, halihazırda indirdiğin bir model içeren bir klasöre de yönlendirebilirsin.

---

## Ayarlar

| Ayar | Açıklama |
|------|----------|
| **Kısayol tuşu** | Herhangi bir tuş veya kombinasyon. Varsayılan: F9 |
| **Konuşma dili** | Belirli bir dili zorla veya Otomatik Algıla'yı kullan |
| **Hassasiyet** | `int8` (varsayılan) · `int8_float32` · `float32` — hız ile doğruluk dengesi |
| **AI ipucu** | Her transkripsiyon için Whisper'a aktarılan bağlam; konuşma dili başına ayrı kaydedilir |
| **Uygulama dili** | Arayüz dili — anında değişir, yeniden başlatma gerekmez |

---

## Gizlilik

Katib, ağdan yalıtılmış ortamlara uygun şekilde tasarlanmıştır:

- Çalışma zamanında dışarıya bağlantı yok
- Kullanım istatistiği, hata raporlama veya güncelleme kontrolü yok
- Ayarlar ve günlükler `%LOCALAPPDATA%\Katib` dizininde yerel olarak saklanır
- Tek ağ etkinliği, isteğe bağlı tek seferlik model indirme işlemidir

---

## Kaynak koddan derleme

```bash
pip install pyinstaller
pyinstaller Katib.spec
```

Çıktı: `dist/Katib/Katib.exe`

---

## Katkıda bulunma

Pull request'ler memnuniyetle karşılanır. Önemli değişiklikler için önce bir issue açarak yaklaşımı tartışalım.

Mimari kararlar [`docs/adr/`](docs/adr/) dizininde belgelenmiştir.

---

*Katib (كاتب) — Arapça'da "katip" anlamına gelir.*

**Lisans:** MIT
