# Katib Geliştirme Süreci ve AI Ajan Kullanım Rehberi

Hoş geldin. Katib projesinde çalışırken AI ajanları sadece kod yazan birer araç değil, seninle omuz omuza çalışan birer "mühendis ortağı" olarak konumlandırıyoruz. Bu doküman, projenin standartlarını korumak ve iş akışını optimize etmek için AI asistanınla (Ajan) nasıl etkileşime girmen gerektiğini tanımlar. 

Aşağıdaki komutlar (skills), karmaşık görevleri standartlaştırılmış ve güvenli bir şekilde yürütmek için tasarlanmış mühendislik yetenekleridir.

---

## 🏗️ Geliştirme Yaşam Döngüsü ve Komutlar

İhtiyacın olan aşamaya göre doğru yeteneği çağırmak, projenin bütünlüğünü korumak için kritiktir.

### 1. Keşif ve Bağlam Kurma (Exploration)
Yeni bir modüle dokunmadan veya uzun süre ara verdiğin bir koda geri dönmeden önce durumu anlamak için bu araçları kullan:
- **`/zoom-out` (Sistem Analizi)**: Kod tabanının haritasını çıkarır. Sinyallerin, worker'ların ve UI bileşenlerinin birbirine nasıl bağlandığını görselleştirir.
- **`/caveman` (Hızlı Odak)**: AI asistanının teknik detaylara odaklanmasını ve gereksiz açıklamalardan kaçınarak doğrudan çözüm üretmesini sağlar.

### 2. Strateji ve Mimari Planlama (Planning)
Bir satır kod yazmadan önce planın sağlamlığından emin olmalısın:
- **`/grill-me` (Tasarım Doğrulama)**: Fikirlerini veya mimari kararlarını AI'a test ettir. AI sana kritik sorular sorarak planındaki zayıf noktaları bulmana yardımcı olur.
- **`/grill-with-docs` (Kural Kaydı)**: Alınan kararların `CONTEXT.md` veya ADR dosyalarına işlenerek projenin kurumsal hafızasına dahil edilmesini sağlar.
- **`/to-prd` (Gereksinim Dokümantasyonu)**: Tartışılan özellikleri uygulanabilir bir Product Requirements Document (PRD) haline getirir.
- **`/to-issues` (Görev Parçalama)**: Büyük bir PRD'yi, birbirini bloklamayan bağımsız geliştirme görevlerine (issues) böler.

### 3. Sorun Giderme ve Teşhis (Troubleshooting)
Hatalarla karşılaştığında sistematik bir yaklaşım izle:
- **`/diagnose` (Derin Teşhis)**: Rastgele hata ayıklamak yerine sisteme geçici sensörler ve loglar yerleştirerek hatanın kaynağını bilimsel yöntemle bulur.
- **`/improve-codebase-architecture` (Mimarî İyileştirme)**: Çalışan ancak teknik borç (tech debt) oluşturan yapıları tespit eder ve refactor önerileri sunar.
- **`/triage` (Hata Yönetimi)**: Biriken hata raporlarını önem ve aciliyet sırasına göre dizeyerek iş listesini temizler.

### 4. Uygulama ve Üretim (Implementation)
Kod yazım aşamasında güvenlik ağlarını asla bırakma:
- **`/tdd` (Güvenli Üretim)**: Önce testi yazıp sonra kodu geliştirerek (Red-Green-Refactor) geriye dönük uyumluluğun bozulmamasını sağlar.
- **`/prototype` (Hızlı Prototipleme)**: Ana kodu kirletmeden, bir fikri doğrulamak için geçici ve izole bir çalışma alanı oluşturur.
- **`/write-a-skill` (Yetenek Sentezi)**: Tekrar eden karmaşık görevler için yeni ve özel bir AI yeteneği tanımlar.

---

## 👨‍🏫 Kıdemli Mühendis Notu (Senior Advice)

AI asistanınla çalışırken şu prensipleri asla unutma:

1.  **Önce Planla, Sonra Yaz:** Her zaman `/grill-me` ile başla. Koda dalmadan önce ne yapacağını AI ile tartışmak, saatlerce sürecek debug seanslarını önler.
2.  **Bağlam En Büyük Güçtür:** AI ajan her oturuma sıfır hafıza ile başlar. Bu yüzden aldığın her kararı `/grill-with-docs` ile `CONTEXT.md`'ye işle. Eğer bir kural orada yazmıyorsa, o kural yoktur.
3.  **Küçük Parçalarla İlerle:** `/to-issues` ile işi böl. Büyük değişiklikler yerine atomik ve test edilebilir adımlarla ilerlemek, sistemin stabilitesini korur.

Bu rehber, senin projeye adaptasyonunu hızlandırmak ve hata payını en aza indirmek için oluşturulmuştur. Herhangi bir sorunda her zaman `CONTEXT.md` dosyasına başvurabilirsin.

---
> *İyi kod yazmak bir yetenekse, iyi plan yapmak bir disiplindir. Disiplinden asla ödün verme.*
