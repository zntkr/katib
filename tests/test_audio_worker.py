import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from workers.audio_worker import AudioWorker, SAMPLE_RATE
from core.audio_source import AudioSource, AudioDeviceError, AudioDisconnectedError

@pytest.fixture
def mock_audio_source():
    source = MagicMock(spec=AudioSource)
    source.native_sample_rate = SAMPLE_RATE
    return source

class TestInitialState:
    def test_starts_clean(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        assert worker._device_index is None
        assert not worker._is_recording
        assert worker._chunks == []

class TestSetDevice:
    def test_set_device_updates_index_and_calls_source(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        mock_audio_source.set_device.return_value = "Test Mic"
        worker.set_device(2)
        assert worker._device_index == 2
        mock_audio_source.set_device.assert_called_once_with(2)

    def test_set_device_handles_error(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        mock_audio_source.set_device.side_effect = AudioDeviceError("Fail")
        worker.set_device(3)
        assert worker._device_index is None

class TestStartRecording:
    def test_start_recording_clears_chunks(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker.set_device(1)
        worker._chunks.append(np.zeros(10))
        worker.start_recording()
        assert worker._chunks == []
        assert worker._is_recording

    def test_start_recording_emits_error_if_no_device(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.start_recording()
        assert "osd.mic_no_device" in errors

    def test_start_recording_handles_source_error(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker.set_device(1)
        mock_audio_source.start.side_effect = AudioDeviceError("Not connected")
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.start_recording()
        assert not worker._is_recording
        assert "osd.mic_not_connected" in errors

class TestStopRecording:
    def test_stop_recording_calls_source_stop(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker.set_device(1)
        worker.start_recording()
    
        # Mock background noise
        for _ in range(5):
            worker._chunks.append(np.zeros(SAMPLE_RATE // 10, dtype=np.float32) + 0.01)
            worker._rms_history.append(0.01)
            
        # Mock speech (loud, exceeding 10dB margin) for at least 0.3 seconds
        for _ in range(5):
            worker._chunks.append(np.zeros(SAMPLE_RATE // 10, dtype=np.float32) + 0.5)
            worker._rms_history.append(0.5)
    
        audio_results = []
        worker.audio_ready.connect(audio_results.append)
    
        worker.stop_recording()
    
        mock_audio_source.stop.assert_called_once()
        assert not worker._is_recording
        assert len(audio_results) == 1

class TestCallbacks:
    def test_audio_callback_appends_chunks(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker._audio_callback(np.ones(10), None)
        assert len(worker._chunks) == 1

    def test_on_stream_finished_unexpected(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker._is_recording = True
        
        errors = []
        worker.error_occurred.connect(errors.append)
        
        worker._on_stream_finished(AudioDisconnectedError("Oops"))
        
        assert not worker._is_recording
        assert "osd.mic_disconnected" in errors

class TestHardwareEvents:
    def test_hardware_event_triggers_refresh(self, qapp, mock_settings, mock_audio_source):
        with patch("PySide6.QtCore.QTimer.singleShot") as mock_timer:
            worker = AudioWorker(mock_settings, mock_audio_source)
            mock_timer.assert_called_once()
            assert mock_timer.call_args[0][1] == worker._init_media_devices

    def test_debounce_timer_calls_refresh(self, qapp, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker._init_media_devices()
        with patch.object(worker, "refresh_devices") as mock_refresh:
            worker._on_audio_inputs_changed()
            assert worker._device_refresh_timer.isActive()
            worker._do_audio_inputs_changed()
            mock_refresh.assert_called_once()
