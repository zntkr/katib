import pytest
from unittest.mock import MagicMock, patch
from workers.audio_worker import AudioWorker

def test_audio_worker_handles_unexpected_disconnect(mock_settings):
    # AudioWorker oluştur
    worker = AudioWorker(settings=mock_settings)
    
    # Sinyalleri dinle
    error_spy = MagicMock()
    level_spy = MagicMock()
    refresh_spy = MagicMock()
    
    worker.error_occurred.connect(error_spy)
    worker.level_changed.connect(level_spy)
    # devices_ready sinyali refresh_devices çağrıldığında atılır
    worker.devices_ready.connect(refresh_spy)
    
    # 1. Senaryo: Beklenmedik bir şekilde stream sonlanırsa (_intentional_close = False)
    worker._intentional_close = False
    
    # _on_stream_finished'i tetikle
    with patch("sounddevice.query_devices", return_value=[]):
        worker._on_stream_finished()
    
    # Doğrulama:
    # - Hata mesajı atılmalı
    error_spy.assert_called_once()
    # - Ses seviyesi 0'a çekilmeli
    level_spy.assert_any_call(0.0)
    # - Cihaz listesi tazelenmeli (bu sinyal refresh_devices içinden gelir)
    # Mevcut kodda refresh_devices ÇAĞRILMIYOR. Bu yüzden bu başarısız olacak (RED).
    refresh_spy.assert_called()
