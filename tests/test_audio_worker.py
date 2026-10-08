import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from workers.audio_worker import AudioWorker, SAMPLE_RATE
from core.audio_source import AudioSource, AudioDeviceError, AudioDisconnectedError
from tests.log_helpers import on_log_entry

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

class TestPartialAudio:
    """Plan 0014: while recording, the recording so far goes out about once a second."""

    def _recording(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker.set_device(1)
        started, partials = [], []
        worker.recording_started.connect(lambda: started.append(True))
        worker.partial_audio.connect(partials.append)
        worker.start_recording()
        return worker, started, partials

    def test_a_recording_that_starts_is_announced(self, mock_settings, mock_audio_source):
        worker, started, _ = self._recording(mock_settings, mock_audio_source)
        assert started == [True] and worker._partial_timer.isActive()

    def test_a_recording_that_fails_to_start_is_not(self, mock_settings, mock_audio_source):
        mock_audio_source.start.side_effect = AudioDeviceError("Not connected")
        worker, started, _ = self._recording(mock_settings, mock_audio_source)
        assert started == [] and not worker._partial_timer.isActive()

    def test_the_recording_so_far_is_sent_as_one_array(self, mock_settings, mock_audio_source):
        worker, _, partials = self._recording(mock_settings, mock_audio_source)
        worker._chunks += [np.ones((1024, 1), dtype=np.float32), np.ones((1024, 1), dtype=np.float32)]
        worker._emit_partial()
        assert len(partials) == 1 and partials[0].shape == (2048,)
        assert len(worker._chunks) == 2  # the recording itself is untouched

    def test_nothing_is_sent_before_the_first_audio(self, mock_settings, mock_audio_source):
        worker, _, partials = self._recording(mock_settings, mock_audio_source)
        worker._emit_partial()
        assert partials == []

    def test_it_stops_with_the_recording(self, mock_settings, mock_audio_source):
        worker, _, partials = self._recording(mock_settings, mock_audio_source)
        worker.stop_recording()
        assert not worker._partial_timer.isActive()

    def test_it_stops_when_the_stream_ends_on_its_own(self, mock_settings, mock_audio_source):
        worker, _, partials = self._recording(mock_settings, mock_audio_source)
        worker._chunks.append(np.ones((1024, 1), dtype=np.float32))
        worker._on_stream_finished(AudioDisconnectedError("gone"))
        worker._emit_partial()
        assert partials == [] and not worker._partial_timer.isActive()


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

class TestRecordingAnalysed:
    """What the settings window is told about every recording (plan 0010): seconds,
    speech dB, noise-floor dB, and the reason when it was dropped."""

    def _record(self, mock_settings, mock_audio_source, levels):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker.set_device(1)
        reports = []
        worker.recording_analysed.connect(lambda *args: reports.append(args))
        worker.start_recording()
        feed = mock_audio_source.start.call_args.args[0]  # the callback the audio source calls
        for level in levels:                              # one 0.1 s block per level
            feed(np.full(SAMPLE_RATE // 10, level, dtype=np.float32), None)
        worker.stop_recording()
        return reports

    def test_a_spoken_recording_is_reported_without_a_problem(self, mock_settings, mock_audio_source):
        [(seconds, speech_db, noise_db, problem)] = self._record(
            mock_settings, mock_audio_source, [0.01] * 5 + [0.5] * 5)
        assert seconds == pytest.approx(1.0)
        assert speech_db == pytest.approx(-6.0, abs=0.1)
        assert noise_db == pytest.approx(-40.0, abs=0.1)
        assert problem == ""

    def test_a_recording_that_is_too_quiet_says_so(self, mock_settings, mock_audio_source):
        [(_, speech_db, _, problem)] = self._record(mock_settings, mock_audio_source, [0.0005] * 10)
        assert speech_db == pytest.approx(-66.0, abs=0.1)
        assert problem == "osd.audio_too_quiet"

    def test_a_recording_that_is_too_short_says_so(self, mock_settings, mock_audio_source):
        [(seconds, _, _, problem)] = self._record(mock_settings, mock_audio_source, [0.5] * 3)
        assert seconds == pytest.approx(0.3)
        assert problem == "osd.recording_too_short"

    def test_an_empty_recording_is_reported_as_too_short(self, mock_settings, mock_audio_source):
        assert self._record(mock_settings, mock_audio_source, []) == [(0.0, -120.0, -120.0, "osd.recording_too_short")]


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


class TestMainThreadTimings:
    """refresh_devices/stop_recording run on the UI thread; their duration is logged
    so real Windows numbers decide whether they must move off it (CONTEXT.md rule 2)."""

    @pytest.mark.parametrize("method", ["refresh_devices", "stop_recording"])
    def test_duration_is_logged(self, mock_settings, mock_audio_source, method):
        mock_audio_source.refresh_devices.return_value = []
        worker = AudioWorker(mock_settings, mock_audio_source)
        logs = []
        on_log_entry(lambda lvl, comp, msg: logs.append(msg))
        getattr(worker, method)()
        assert any("completed:" in m and "ms" in m for m in logs)


class TestStartLatency:
    """Plan 0006 Faz 1: how long after start_recording() the first audio chunk arrives."""

    def test_first_chunk_latency_is_logged_once(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker.set_device(1)
        logs = []
        on_log_entry(lambda lvl, comp, msg: logs.append(msg))
        worker.start_recording()
        worker._audio_callback(np.ones(1024, dtype=np.float32) * 0.1, None)
        worker._audio_callback(np.ones(1024, dtype=np.float32) * 0.1, None)
        latency = [m for m in logs if m.startswith("First audio after")]
        assert len(latency) == 1
        assert latency[0].endswith(" ms")


class TestChunkOwnership:
    """Plan 0012 Faz 6: the source already hands over its own copy; the worker does not copy again."""

    def test_a_chunk_is_kept_as_the_source_handed_it_over(self, mock_settings, mock_audio_source):
        worker = AudioWorker(mock_settings, mock_audio_source)
        worker.set_device(1)
        worker.start_recording()
        chunk = np.ones(1024, dtype=np.float32) * 0.1
        worker._audio_callback(chunk, None)
        assert worker._chunks[0] is chunk
