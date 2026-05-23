# ADR-0003: Sinyal Kablolaması main.py'de Merkezi Kalır

## Durum
Kabul edildi.

## Bağlam
`main.py` içindeki `_deferred_init()` fonksiyonu, tüm Worker→UI ve Dashboard→Worker sinyal bağlantılarını (~50 satır) tek bir blokta kurar. Bu yapıyı refactor etme — örneğin her Worker'a `connect_to(tray, dashboard, osd)` metodu eklemek veya bir bağlantı manifest'i oluşturmak — gündeme geldi.

İnsan geliştirici projelerinde bu refactor makul görünür: "bir sinyalin nereye gittiğini anlamak için 3 dosya açmak gerekiyor" bir keşif friksiyonudur. Ancak bu proje **tamamen AI ajanları tarafından geliştirilmektedir** (bkz. CONTEXT.md — Geliştirme Modeli). AI ajan grep ve paralel dosya okuma ile bu friksiyonu saniyeler içinde aşar; kod lokalitesi insan belleği için değerlidir (7±2 sınırı), ajan için değil.

## Karar
Sinyal kablolaması `main.py`'de merkezi ve düz (flat) kalacaktır. Soyutlama yapılmayacaktır.

Gerekçe:
- **İzlenebilirlik korunur:** Tüm bağlantılar tek bir yerde — ajan veya insan hangi sinyalin nereye gittiğini `main.py`'yi okuyarak anlar.
- **Katman ihlali önlenir:** `Worker.connect_to(dashboard)` yaklaşımı Worker'ların UI tiplerini import etmesini gerektirir — bu mimari kuralı ihlal eder.
- **CONTEXT.md'deki Anti-Pattern #2 ile tutarlı:** "Sinyal kablolamasının 100 satır sürmesi, soyutlanmasından daha iyidir."

## Sonuçlar
- Yeni bir Worker eklendiğinde `_deferred_init()` içindeki bağlantı bloğu elle güncellenmeli ve ilgili testler yazılmalıdır.
- Sessiz kopuş riski (sinyal adı değişirse bağlantı fark edilmeden kopar) kabul edilmiş bir risk olarak kalır; test suite bu riski azaltır.
- Bu karar AI-ajan geliştirme bağlamına özgüdür. Projeye insan geliştirici dahil olursa yeniden değerlendirilmelidir.
