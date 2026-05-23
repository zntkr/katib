# ADR 0005: Minimalist UX ve Örtük Durum Sıfırlama (Implicit State Reset)

## Durum
Kabul Edildi.

## Bağlam
AudioWorker üzerinden sağlanan mikrofon listesinde (ComboBox), kullanıcının bir cihaza "sabitlenmesi" (mühürlenmesi) ve sonrasında "Sistem Varsayılanını Takip Et" moduna geri dönebilmesi gerekiyordu.

Varsayılana dönüş için; UI'a ekstra bir "Temizle/Sıfırla" butonu koymak veya ComboBox'ın en üstüne "Sistem Varsayılanı" şeklinde sanal bir boş öğe yerleştirmek (UserData=None) masaya yatırıldı. Ancak Katib'nin Minimalist HUD (Compact UI) tasarım anlayışında her ekstra buton, görsel gürültü (visual noise) ve kullanıcının öğrenmesi gereken ekstra bir kavram anlamına gelir.

## Karar
"Do What I Mean" (Ne demek istediğimi yap) prensibi benimsendi.
Kullanıcı zaten "(Varsayılan)" ibaresi taşıyan bir listeleme öğesine tıkladığında, bu doğal etkileşim arka planda (implicit) ayarları sıfırlamak ve cihaz sabitlemesini (mührünü) kaldırmak için bir tetikleyici olarak kullanılmıştır.

## Sonuçlar
- **Avantajlar:** 
  - Arayüze hiçbir ekstra buton veya açıklama eklenmedi (Aşırı mühendislikten kaçınıldı).
  - ComboBox saf ve sadece "donanımları" listeleyen yapısını korudu.
  - Kullanıcı için oldukça sezgisel bir deneyim ("Ben işletim sisteminin seçtiğini istiyorum" hissi) sağlandı.
- **Dezavantajlar / Riskler:** 
  - Bu davranışın arayüzde açıkça "Bu butona basarsan sıfırlanır" diye yazmaması, bazı kullanıcılar için "gizli özellik" gibi algılanabilir. Ancak sistem zaten varsayılan ile başlatıldığı için, kullanıcı ayarı bozsa dahi kolayca varsayılana dönmenin yolunu (aynı öğeye tekrar tıklayarak) bulacaktır.

## Referans
`CONTEXT.md` - Anti-Patterns: Aşırı UI Elemanı (Over-UI) ve Minimalist UX.