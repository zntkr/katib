# ADR-0002: Offline-First ve Gizlilik Politikası

## Durum
Kabul edildi.

## Bağlam
Katib uygulamasının temel vaatlerinden biri kullanıcı gizliliği ve verilerin yerelde işlenmesidir (Local-first). Uygulamanın arka planda dış sunucularla (GitHub, analitik servisleri vb.) iletişim kurması, bu güveni zedeleyebilir ve kurumsal/güvenli ortamlarda kullanımı engelleyebilir.

## Karar
Uygulama, **Offline-First** felsefesini benimseyecektir. 
- Hiçbir otomatik güncelleme kontrolü (update check) yapılmayacaktır.
- Telemetri, analitik veya "heartbeat" gibi arka plan ağ istekleri eklenmeyecektir.
- Tek istisna, kullanıcının açık talebiyle (Ayarlar panelinden buton tıklamasıyla) HuggingFace üzerinden model indirilmesidir.

## Sonuçlar
- Uygulama "air-gapped" senaryolarda güvenle kullanılabilir.
- Güncellemeler kullanıcı tarafından manuel olarak (GitHub üzerinden takip edilerek) yapılmalıdır.
- Bakım maliyeti düşer (API değişikliklerine bağımlılık azalır).
