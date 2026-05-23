import pytest
from unittest.mock import patch, MagicMock
import sys
import gc
import logging

# Globally mock sounddevice for environments where it is not installed
sys.modules['sounddevice'] = MagicMock()

from core.settings import SettingsManager

@pytest.fixture
def mock_settings(tmp_path):
    """
    Tüm testlerde kullanılacak, diske yazmayan bellek içi SettingsManager.
    Ayrıca get_settings_path'i tmp_path'e yönlendirerek güvenliği garantiye alır.
    """
    path = tmp_path / "settings.json"
    with patch("core.settings.get_settings_path", return_value=path):
        sm = SettingsManager(in_memory=True)
        # Sık kullanılan varsayılan ayarları dolduralım (eski testlerin beklediği durumlar)
        sm.set("hotkey", "f9")
        sm.set("language", "auto")
        sm.set("compute_type", "int8")
        sm.set("beam_size", 5)
        sm.set("vad_threshold", 0.5)
        yield sm

@pytest.fixture(scope="session")
def qapp():
    """Provides a QApplication instance for tests if pytest-qt is not installed."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture(autouse=True)
def _stub_qt_os_hooks():
    """QMediaDevices Windows IMMDeviceEnumerator hook'unu devre dışı bırakır.
    Aksi takdirde test bitiminde COM thread process'i bloke eder."""
    with patch("PySide6.QtMultimedia.QMediaDevices", MagicMock):
        yield


@pytest.fixture(autouse=True)
def _flush_qt_deletelater(qapp):
    """Her testten sonra deleteLater() kuyruğunu boşaltır.
    Birikmiş QWidget nesneleri çoklu test dosyalarında hang'e yol açar."""
    yield
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()

@pytest.fixture(autouse=True)
def _cleanup_qthreads():
    """Her testten sonra bellekte asılı kalan QThread/Worker nesnelerini bulup güvenlice kapatır.
    Segmentation Fault ve Test Hang (donma) risklerini tamamen ortadan kaldırır."""
    yield
    from PySide6.QtCore import QThread
    
    # Bellekteki (Garbage Collector) tüm objeleri tara
    for obj in gc.get_objects():
        try:
            if isinstance(obj, QThread) and obj.isRunning():
                logging.warning(f"TEARDOWN UYARISI: Açık unutulan QThread yakalandı ve kapatılıyor -> {obj}")
                
                # Eğer Worker kendi özel stop metoduna sahipse (örn. AudioWorker) onu kullan
                if hasattr(obj, "stop"):
                    stop_method = getattr(obj, "stop")
                    if callable(stop_method):
                        stop_method()
                    
                obj.quit()
                obj.wait(1000) # 1 saniye bekle, kilitlenirse zorla bırak
        except (ReferenceError, RuntimeError):
            # C++ objesi zaten silinmişse hatayı yoksay
            pass
