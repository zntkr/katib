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
    """Mute sinyalinin 1.5 sn'den önce fırlatılmadığını, sonrasında fırlatıldığını doğrular."""
    settings = MockSettings()
    worker = AudioWorker(settings)
    spy = QSignalSpy(worker.muted_detected)
    silent_data = np.zeros(1024, dtype=np.float32)
    
    with patch("winsound.Beep"):
        # İlk çağrı: Timer başlar
        worker._audio_callback(silent_data, 1024, None, 0)
        
        with patch.object(worker._silence_timer, "elapsed", return_value=1000):
            worker._audio_callback(silent_data, 1024, None, 0)
        assert spy.count() == 0, "Mute sinyali 1.5 sn dolmadan fırlatıldı!"

        with patch.object(worker._silence_timer, "elapsed", return_value=1600):
            worker._audio_callback(silent_data, 1024, None, 0)
        assert spy.count() >= 1, "Mute sinyali 1.5 sn geçmesine rağmen fırlatılmadı!"

def test_audio_worker_whisper_tolerance():
    """Çok düşük sinyal (fısıltı/gürültü) varken alarm verilmediğini doğrular."""
    settings = MockSettings()
    worker = AudioWorker(settings)
    spy = QSignalSpy(worker.muted_detected)
    
    # Mutlak sıfır değil, ama çok düşük bir gürültü (1e-5)
    noise_data = np.ones(1024, dtype=np.float32) * 0.00001
    
    # Gürültü timer'ı hiç başlatmamalı, döngüye gerek yok
    worker._audio_callback(noise_data, 1024, None, 0)
    worker._audio_callback(noise_data, 1024, None, 0)
    
    assert spy.count() == 0, "Düşük sinyal (fısıltı) varken Mute alarmı verildi!"

def test_audio_worker_recovery_from_silence():
    """Ses gelmeye başladığında sessizlik uyarısının sıfırlandığını doğrular."""
    settings = MockSettings()
    worker = AudioWorker(settings)
    
    # Önce sessizlik
    silent_data = np.zeros(1024, dtype=np.float32)
    worker._audio_callback(silent_data, 1024, None, 0)
    assert worker._silence_timer.isValid() is True
    
    # Sonra ses (Yüksek RMS)
    loud_data = np.ones(1024, dtype=np.float32) * 0.5
    worker._audio_callback(loud_data, 1024, None, 0)
    
    assert worker._silence_notified is False
    assert worker._silence_timer.isValid() is False
