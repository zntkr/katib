import pytest
from unittest.mock import MagicMock, patch
from workers.audio_worker import AudioWorker

def test_audio_worker_handles_unexpected_disconnect(mock_settings):
    # Create AudioWorker
    worker = AudioWorker(settings=mock_settings)

    # Listen to signals
    error_spy = MagicMock()
    level_spy = MagicMock()
    refresh_spy = MagicMock()

    worker.error_occurred.connect(error_spy)
    worker.level_changed.connect(level_spy)
    # devices_ready signal is emitted when refresh_devices is called
    worker.devices_ready.connect(refresh_spy)

    worker._intentional_close = False

    # trigger _on_stream_finished
    with patch("sounddevice.query_devices", return_value=[]):
        worker._on_stream_finished()

    # Verification:
    # - Error message must be emitted
    error_spy.assert_called_once()
    # - Audio level must be reset to 0
    level_spy.assert_any_call(0.0)
    # - Device list must be refreshed (this signal comes from inside refresh_devices)
    # In the current code refresh_devices is NOT called. This will fail (RED).
    refresh_spy.assert_called()
