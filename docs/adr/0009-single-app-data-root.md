# ADR-0009: Tüm Uygulama Verisi için Tek Kök Klasör

## Durum
Kabul edildi.

## Bağlam
Katib verisini üç farklı köke dağıtıyordu:

- Ayarlar: `~/.katib_app/settings.json`
- Modeller: `~/.katib_app/models`
- Loglar: `%LOCALAPPDATA%\Katib\Logs`

Bu dağınıklık iki somut hataya yol açtı:

1. `docs/guides/enterprise_deployment.md`, BT ekiplerine modelleri `%USERPROFILE%\Katib\Models` klasörüne kopyalamalarını söylüyordu. Kod bu klasöre hiç bakmadığı için kılavuza uyan kurumsal dağıtımlarda Katib "model yok" diyordu. Kılavuzdaki örnek klasör adı (`systran-faster-whisper-small`) da koddaki adla (`faster-whisper-small`) uyuşmuyordu.
2. Log yolu iki yerde ayrı hesaplanıyordu (`main.py` ve `ui/settings_dialog.py`) ve Linux'ta iki farklı klasörü gösteriyordu.

Ayrıca 10 dildeki README, "ayarlar ve loglar `%LOCALAPPDATA%\Katib` içinde" diyordu; ayarlar için bu yanlıştı.

## Karar
Tüm uygulama verisi tek bir kökte tutulur:

```
%LOCALAPPDATA%\Katib\          (Linux: $XDG_DATA_HOME/Katib, varsayılan ~/.local/share/Katib)
├── settings.json
├── Models\<model-klasörü>\
└── Logs\katib.log
```

- Kök yalnızca `core/settings.py` içindeki `get_app_data_dir()` fonksiyonunda hesaplanır. `get_settings_path()`, `get_log_dir()` ve `DEFAULT_DOWNLOAD_PARENT` ondan türetilir. Başka hiçbir yerde yol birleştirilmez.
- Eski kurulumlardan kalan `~/.katib_app` verisi, açılışta `SettingsManager`'dan önce çalışan `migrate_legacy_data()` ile bir kez taşınır. Taşıma asla uygulamayı çökertmez; taşınamayan bir model yerinde kalır ve `model_dir` onu gösterecek şekilde ayarlanır.
- `tests/test_paths.py::TestEnterpriseGuide`, kurumsal kılavuzdaki yolun ve model klasör adlarının koddakiyle eşleştiğini doğrular.

Gerekçe:
- **`%LOCALAPPDATA%`, Windows'ta doğru yerdir:** Modeller 3 GB'a kadar çıkar; dolaşan (roaming) profille taşınmamalıdır. `%LOCALAPPDATA%` tam olarak bunun için vardır.
- **Loglar ve README'ler zaten buradaydı:** En az değişiklikle tutarlılık sağlanır.

## Reddedilen Alternatifler
- **Yalnızca kılavuzu `~/.katib_app`'e göre düzeltmek:** En ucuz seçenekti, ancak README'ler yanlış ve kökler dağınık kalırdı; kullanıcı ana klasöründe gizli bir klasör Windows teamüllerine de aykırıdır.
- **Eski klasörü ek tarama konumu olarak kalıcı tutmak:** Taşıma başarısızlığında bile modelin çalışmasını sağlar, ancak `ModelProvider`'a kalıcı ikinci bir yol ekler. Bunun yerine taşıma sırasında `model_dir` somut modele yönlendirilir.

## Sonuçlar
- Yeni bir dosya yolu gerekiyorsa `get_app_data_dir()` altında türetilmelidir; `Path.home()` veya ortam değişkenleriyle yeniden yol hesaplanmamalıdır.
- Makine geneli (tüm kullanıcılar için ortak) bir model klasörü, örn. `C:\ProgramData\Katib\Models`, bu kararın kapsamı dışındadır.
