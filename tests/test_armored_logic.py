import pytest
import sys
import numpy as np
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtTest import QSignalSpy
from workers.audio_worker import AudioWorker

# Global app instance for tests — QApplication required for theme/palette support
app = QApplication.instance() or QApplication(sys.argv)

class MockSettings:
    def __init__(self):
        self.data = {"min_audio_rms": 0.005}
    def get(self, key, default=None):
        return self.data.get(key, default)

def test_audio_worker_mute_timing_accuracy():
    """Verifies that the mute signal is not emitted before 1.5 s but is emitted after."""
    settings = MockSettings()
    worker = AudioWorker(settings)
    spy = QSignalSpy(worker.muted_detected)
    silent_data = np.zeros(1024, dtype=np.float32)

    with patch("winsound.Beep"):
        # First call: timer starts
        worker._audio_callback(silent_data, 1024, None, 0)

        with patch.object(worker._silence_timer, "elapsed", return_value=1000):
            worker._audio_callback(silent_data, 1024, None, 0)
        assert spy.count() == 0, "Mute signal emitted before 1.5 s elapsed!"

        with patch.object(worker._silence_timer, "elapsed", return_value=1600):
            worker._audio_callback(silent_data, 1024, None, 0)
        assert spy.count() >= 1, "Mute signal not emitted even after 1.5 s!"

def test_audio_worker_whisper_tolerance():
    """Verifies that no alarm is raised when signal is very low (whisper/noise)."""
    settings = MockSettings()
    worker = AudioWorker(settings)
    spy = QSignalSpy(worker.muted_detected)

    # Not absolute zero, but very low noise (1e-5)
    noise_data = np.ones(1024, dtype=np.float32) * 0.00001

    # Noise must not start the timer; no loop needed
    worker._audio_callback(noise_data, 1024, None, 0)
    worker._audio_callback(noise_data, 1024, None, 0)

    assert spy.count() == 0, "Mute alarm raised while low signal (whisper) was present!"

def test_audio_worker_recovery_from_silence():
    """Verifies that the silence warning is reset when audio resumes."""
    settings = MockSettings()
    worker = AudioWorker(settings)

    # First: silence
    silent_data = np.zeros(1024, dtype=np.float32)
    worker._audio_callback(silent_data, 1024, None, 0)
    assert worker._silence_timer.isValid() is True

    # Then: audio (high RMS)
    loud_data = np.ones(1024, dtype=np.float32) * 0.5
    worker._audio_callback(loud_data, 1024, None, 0)

    assert worker._silence_notified is False
    assert worker._silence_timer.isValid() is False
