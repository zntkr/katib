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
    In-memory SettingsManager that does not write to disk, used across all tests.
    Also redirects get_settings_path to tmp_path to guarantee isolation.
    """
    path = tmp_path / "settings.json"
    with patch("core.settings.get_settings_path", return_value=path):
        sm = SettingsManager(in_memory=True)
        # Populate frequently used default settings (expected by legacy tests)
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
def _init_i18n():
    """Sets the default language to English for all tests."""
    from core.i18n import set_language
    set_language("en")


@pytest.fixture(autouse=True)
def _stub_qt_os_hooks():
    """Disables the QMediaDevices Windows IMMDeviceEnumerator hook.
    Otherwise the COM thread blocks the process at test teardown."""
    with patch("PySide6.QtMultimedia.QMediaDevices", MagicMock):
        yield


@pytest.fixture(autouse=True)
def _flush_qt_deletelater(qapp):
    """Flushes the deleteLater() queue after each test.
    Accumulated QWidget objects can cause hangs across multiple test files."""
    yield
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()

@pytest.fixture(autouse=True)
def _cleanup_qthreads():
    """Finds and safely shuts down any QThread/Worker objects lingering in memory after each test.
    Completely eliminates the risk of Segmentation Faults and test hangs."""
    yield
    from PySide6.QtCore import QThread

    # Scan all objects tracked by the garbage collector
    for obj in gc.get_objects():
        try:
            if isinstance(obj, QThread) and obj.isRunning():
                logging.warning(f"TEARDOWN WARNING: Leaked running QThread detected and closing -> {obj}")

                # If the Worker has its own stop method (e.g. AudioWorker), use it
                if hasattr(obj, "stop"):
                    stop_method = getattr(obj, "stop")
                    if callable(stop_method):
                        stop_method()

                obj.quit()
                obj.wait(1000) # wait 1 second; force-release if deadlocked
        except (ReferenceError, RuntimeError):
            # Ignore errors if the C++ object has already been deleted
            pass
