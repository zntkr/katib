import threading
import pytest
from PySide6.QtCore import QCoreApplication
from unittest.mock import MagicMock, patch
from workers.audio_worker import AudioWorker

def test_audio_worker_handles_unexpected_disconnect(mock_settings):
    # Create AudioWorker
    worker = AudioWorker(settings=mock_settings, audio_source=MagicMock())

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
        worker._on_stream_finished(Exception('disconnect'))

    # Verification:
    # - Error message must be emitted
    error_spy.assert_called_once()
    # - Audio level must be reset to 0
    level_spy.assert_any_call(0.0)
    # - Device list must be refreshed, but only after the callback has returned
    #   (it re-initialises PortAudio, which is forbidden inside a stream callback)
    refresh_spy.assert_not_called()
    QCoreApplication.processEvents()
    refresh_spy.assert_called()


def test_disconnect_from_portaudio_thread_refreshes_on_main_thread(mock_settings):
    source = MagicMock()
    source.refresh_devices.side_effect = lambda: refresh_threads.append(threading.current_thread()) or []
    refresh_threads = []
    worker = AudioWorker(settings=mock_settings, audio_source=source)

    t = threading.Thread(target=worker._on_stream_finished, args=(Exception("disconnect"),))
    t.start()
    t.join()
    assert refresh_threads == []  # nothing ran on the callback thread

    QCoreApplication.processEvents()
    assert refresh_threads == [threading.main_thread()]


def test_intentional_close_does_not_refresh(mock_settings):
    source = MagicMock()
    worker = AudioWorker(settings=mock_settings, audio_source=source)
    worker._on_stream_finished(None)
    QCoreApplication.processEvents()
    source.refresh_devices.assert_not_called()
