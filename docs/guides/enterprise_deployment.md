# Katib: Kurumsal Dağıtım Kılavuzu (Enterprise Deployment)

Bu kılavuz, Katib uygulamasını kısıtlı ağlara, güvenlik duvarlarına veya Zscaler gibi katı proxy kurallarına sahip şirket ağlarında dağıtmakla görevli IT (Bilgi İşlem) departmanları için hazırlanmıştır.

Katib, varsayılan olarak Speech-to-Text (STT) modellerini Hugging Face üzerinden çalışma zamanında (runtime) indirir. Ancak şirket ağlarında `huggingface.co` engelli olduğunda indirmeler başarısız olabilir. Bu durumu yönetmek için en sağlıklı yöntem **"Thin Exe + Model Sideloading" (Hafif Çalıştırılabilir Dosya + Modeli Dışarıdan Yükleme)** stratejisidir.

---

## 1. Mimari Yaklaşım (Thin Exe + Sideload)

Uygulamanın kendisini (.exe) ve devasa dil modelini (örneğin 1.5 GB boyutundaki Whisper modelini) tek bir `.exe` içine **GÖMMEYİN (Fat Exe)**. Bu yöntem uygulamanın açılış hızını dramatik ölçüde düşürür ve her küçük arayüz güncellemesinde kullanıcılara gigabaytlarca veri göndermenizi gerektirir.

Bunun yerine:
1. Katib'i standart, hafif bir `.exe` olarak derleyin (~50-70 MB).
2. Kullanılacak yapay zeka modelini ağ üzerinden (GPO, SCCM, MECM vb.) ayrı bir klasör olarak kullanıcıların bilgisayarına kopyalayın.

Katib, açılışta modelleri otomatik olarak tarar ve bulduğu an kullanıma hazır hale getirir.

---

## 2. Dağıtım Adımları (GPO / SCCM)

### Adım 2.1: Model Dosyalarını Hazırlama
Öncelikle ağ kısıtlaması olmayan bir bilgisayarda (veya kişisel cihazınızda) Katib'in kullanacağı modeli indirin.
Katib'in modelleri varsayılan olarak şu klasörde saklanır:
`C:\Users\<KullaniciAdi>\Katib\Models`

İndirdiğiniz modelin klasör yapısı şu şekilde görünmelidir:
```text
Katib\Models\
└── systran-faster-whisper-small\
    ├── config.json
    ├── model.bin
    ├── preprocessor_config.json
    ├── tokenizer.json
    └── vocabulary.txt
```

### Adım 2.2: Kullanıcılara Dağıtım (Push)
SCCM, MECM veya Group Policy (GPO) kullanarak hazırladığınız bu model klasörünü şirket içi cihazlardaki aynı hedef yola kopyalayan bir dağıtım kuralı oluşturun:
`%USERPROFILE%\Katib\Models\`

*Not: Uygulama açılışta bu dizini otomatik tarayacaktır. Kullanıcının arayüzden ek bir ayar yapmasına gerek yoktur.*

---

## 3. Kullanıcı Deneyimi ve Hata Yönetimi (Yumuşak Mod)

Katib arayüzündeki **"Download" (İndir)** veya model seçim ekranları şirket içi dağıtımlarda **gizlenmemiştir** (Yumuşak Mod).

- Eğer IT departmanı modeli yukarıdaki adımlardaki gibi doğru yere kopyalamışsa, Katib açılışta modeli bulur ve durum çubuğu `Ready` (Hazır) olarak güncellenir.
- Eğer kullanıcı Hugging Face'in engelli olduğu ağda manuel olarak "Download" butonuna basarsa standart bir bağlantı hatası (Connection Error / OSD uyarıları) alacaktır. Uygulama çökmeyecektir.
- Kurum içi Helpdesk dokümanlarınıza: *"Model inmiyor hatası alıyorsanız IT destek bileti açın, modeli cihazınıza yetkili yükleyecektir"* şeklinde bir not düşmeniz tavsiye edilir.

---

## 4. Özel Sertifikalar (Proxy/Zscaler Desteği)

Katib, Python'un `truststore` kütüphanesini kullanacak şekilde tasarlanmıştır. Bu sayede Windows'un işletim sistemi seviyesindeki sertifika deposunu (Windows Certificate Store) kullanır. Şirketinizin Zscaler veya benzeri bir aracı proxy sertifikası işletim sistemine yüklüyse, Katib TLS/SSL bağlantılarında (API çağrıları vb.) sorun yaşamaz. Ekstra bir sertifika eklemenize veya `.pem` yapılandırmasına gerek yoktur.
