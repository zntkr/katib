"""
GPU'da model değişimi denetimi (plan 0009).

Katib'in gerçek yükleme yolunu (TranscriptionWorker._load_model) gerçek
modellerle ve gerçek ekran kartında çalıştırır: A → B → A → B, ardından
GPU'dan CPU'ya dönüş, ardından yeniden GPU.

Neden var: 2026-10-09'da RTX 4080'de Katib, inen modele geçerken çöktü.
GPU'da çalışmış bir CTranslate2 modelini yok etmek süreci öldürüyordu
(konuşma dili "tr" iken; otomatik algılamada değil). Düzeltme
`TranscriptionWorker._release_model` içindedir. Testler GPU kullanamaz
(tests/conftest.py::_no_gpu), bu yüzden GPU'ya dokunan her değişiklikten
sonra bu betik elle çalıştırılır.

Kullanım (proje kökünden, NVIDIA kartlı makinede):

    .venv\\Scripts\\python scripts\\gpu_model_degisimi.py <model klasörü A> <model klasörü B>
    .venv\\Scripts\\python scripts\\gpu_model_degisimi.py A B --dil auto

Başarı: son satır "TAMAM". Çökerse süreç hiçbir şey söylemeden biter: son
satır bir "yükleniyor" satırı olarak kalır ve çıkış kodu sıfır olmaz.

Ayarlar bellekte tutulur; settings.json okunmaz ve yazılmaz. Mikrofon açılmaz.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def kart_bellegi() -> str:
    """Kartın toplam bellek kullanımı; nvidia-smi yoksa boş."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    return f" | kart {out}" if out else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="GPU'da model değişimi denetimi")
    parser.add_argument("model_a", type=Path)
    parser.add_argument("model_b", type=Path)
    parser.add_argument("--dil", default="tr", help="konuşma dili; çökme 'tr' ile görüldü (varsayılan: tr)")
    args = parser.parse_args()

    from PySide6.QtCore import QCoreApplication
    from core.models import ModelProvider
    from core.settings import SettingsManager
    from workers.transcription_worker import TranscriptionWorker

    app = QCoreApplication(sys.argv)  # noqa: F841 - sinyaller için gerekli
    settings = SettingsManager(in_memory=True)
    settings.set("language", args.dil)
    provider = ModelProvider(args.model_a.parent, active_model_path=str(args.model_a))
    worker = TranscriptionWorker(settings, provider)
    yuklenen: list[tuple[str, str]] = []
    worker.model_loaded.connect(lambda cihaz, tip, _not: yuklenen.append((cihaz, tip)))

    def yukle(baslik: str, **kwargs) -> None:
        print(f"{baslik} yükleniyor...", flush=True)
        worker._load_model(**kwargs)
        durum = "/".join(yuklenen[-1]) if worker.is_ready else "YÜKLENEMEDİ"
        print(f"    {durum}{kart_bellegi()}", flush=True)
        if not worker.is_ready:
            sys.exit(1)

    for adim, model in enumerate((args.model_a, args.model_b, args.model_a, args.model_b), start=1):
        settings.set("model_dir", str(model))
        provider.active_model_path = str(model)
        yukle(f"{adim}. {model.name}")
    yukle("5. GPU'dan CPU'ya dönüş:", allow_gpu=False)
    yukle("6. Yeniden GPU:")

    if "cuda" not in {cihaz for cihaz, _ in yuklenen}:
        print("UYARI: model hiç GPU'da çalışmadı; bu makinede denetimin anlamı yok.")
    print("TAMAM", flush=True)
    os._exit(0)  # Katib de böyle çıkar; yıkıcılar çalışmaz


if __name__ == "__main__":
    main()
