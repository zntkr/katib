"""
AudioWorker tests.
sounddevice.InputStream is mocked; no microphone required.
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from workers.audio_worker import AudioWorker, SAMPLE_RATE, _PortAudioError

class TestInitialState:
    def test_device_index_starts_none(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        assert worker._device_index is None

    def test_stream_starts_none(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        assert worker._stream is None

    def test_chunks_start_empty(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        assert worker._chunks == []

    def test_stop_event_starts_unset(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        assert not worker._stop_event.is_set()


class TestSetDevice:
    def test_set_device_updates_index(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker.set_device(2)
        assert worker._device_index == 2

    def test_set_device_emits_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        with patch("workers.audio_worker.sd.query_devices", side_effect=Exception("no device")):
            worker.set_device(3)
        assert any("3" in msg for msg in logs)


class TestStartRecording:
    def test_start_recording_clears_chunks(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        dummy = np.zeros((1024, 1), dtype="float32")
        worker._chunks.append(dummy)

        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream = MagicMock()
            mock_stream_cls.return_value = mock_stream
            worker.start_recording()

        assert worker._chunks == []

    def test_start_recording_twice_opens_one_stream(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream = MagicMock()
            mock_stream_cls.return_value = mock_stream
            worker.start_recording()
            worker.start_recording()   # second call should be ignored

        assert mock_stream_cls.call_count == 1

    def test_start_recording_emits_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream_cls.return_value = MagicMock()
            worker.start_recording()
        assert any("started" in m.lower() for m in logs)

    def test_start_recording_emits_error_on_failure(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        errors = []
        worker.error_occurred.connect(errors.append)
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream", side_effect=Exception("device unavailable")):
            worker.start_recording()
        assert len(errors) == 1
        assert "osd.mic_open_failed" in errors[0]

    def test_stream_is_none_after_error(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream", side_effect=Exception("error")):
            worker.start_recording()
        assert worker._stream is None

    def test_start_recording_fallback_on_portaudio_error(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker.set_device(1)
        
        mock_dev_info = {"default_samplerate": 48000.0}
        
        def mock_stream_cls(*args, **kwargs):
            if kwargs.get("samplerate") == 16000:
                raise _PortAudioError("Invalid sample rate")
            return MagicMock()
            
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.query_devices", return_value=mock_dev_info), \
             patch("sounddevice.InputStream", side_effect=mock_stream_cls):
             
             worker.start_recording()
             assert worker._native_sr == 48000
             assert worker._stream is not None

    def test_start_recording_fallback_fails(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker.set_device(1)
        mock_dev_info = {"default_samplerate": 48000.0}

        def mock_stream_cls(*args, **kwargs):
            raise _PortAudioError("Invalid sample rate")

        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.query_devices", return_value=mock_dev_info), \
             patch("sounddevice.InputStream", side_effect=mock_stream_cls):

             worker.start_recording()
             assert worker._stream is None

    def test_invalid_device_error_skips_fallback(self, qapp, mock_settings):
        """paInvalidDevice (-9996): fallback must not be attempted; 'mic not connected' must be reported."""
        worker = AudioWorker(mock_settings)
        worker.set_device(1)
        errors = []
        stream_open_count = 0
        worker.error_occurred.connect(errors.append)

        def mock_stream_cls(*args, **kwargs):
            nonlocal stream_open_count
            stream_open_count += 1
            raise _PortAudioError("Error opening InputStream: Invalid device [PaErrorCode -9996]")

        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream", side_effect=mock_stream_cls):
            worker.start_recording()

        assert stream_open_count == 1, "Fallback must not be attempted"
        assert errors == ["osd.mic_not_connected"]
        assert worker._stream is None

class TestStopRecording:
    def test_stop_recording_when_not_recording_does_nothing(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        worker.stop_recording()   # stream is None → early return
        assert not any("Recording complete" in m for m in logs)

    def test_stop_recording_empty_chunks_no_signal(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        ready = []
        worker.audio_ready.connect(ready.append)

        mock_stream = MagicMock()
        worker._stream = mock_stream
        # leave _chunks empty
        worker.stop_recording()
        assert len(ready) == 0

    def test_stop_recording_emits_audio_ready(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        ready = []
        worker.audio_ready.connect(ready.append)

        mock_stream = MagicMock()
        worker._stream = mock_stream

        chunk = np.ones((1024, 1), dtype="float32") * 0.5
        for _ in range(10):
            worker._chunks.append(chunk)

        worker.stop_recording()
        assert len(ready) == 1

    def test_stop_recording_output_is_1d(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        received = []
        worker.audio_ready.connect(received.append)

        mock_stream = MagicMock()
        worker._stream = mock_stream

        chunk = np.ones((1024, 1), dtype="float32")
        for _ in range(10):
            worker._chunks.append(chunk)

        worker.stop_recording()
        assert received[0].ndim == 1

    def test_stop_recording_correct_length(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        received = []
        worker.audio_ready.connect(received.append)

        mock_stream = MagicMock()
        worker._stream = mock_stream

        chunk = np.ones((1024, 1), dtype="float32")
        n_chunks = 10
        for _ in range(n_chunks):
            worker._chunks.append(chunk)

        worker.stop_recording()
        assert len(received[0]) == 1024 * n_chunks

    def test_stop_recording_correct_duration_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))

        mock_stream = MagicMock()
        worker._stream = mock_stream

        # 1 second of audio: 16000 frames
        chunk = np.ones((SAMPLE_RATE, 1), dtype="float32")
        worker._chunks.append(chunk)

        worker.stop_recording()
        assert any("1.0" in m for m in logs)

    def test_stop_recording_resamples_if_native_sr_different(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._native_sr = 48000
        worker._stream = MagicMock()
        worker._chunks.append(np.ones((24000, 1), dtype="float32")) # 0.5 seconds
        
        ready = []
        worker.audio_ready.connect(ready.append)
        
        mock_settings.set("vad_threshold", 0.0)
        worker.stop_recording()
            
        assert len(ready) == 1
        assert len(ready[0]) == 8000  # size after downsampling from 48k to 16k


class TestAudioCallback:
    def test_callback_appends_chunk(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        indata = np.ones((1024, 1), dtype="float32") * 0.3
        worker._audio_callback(indata, 1024, None, None)
        assert len(worker._chunks) == 1

    def test_callback_copies_data(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        indata = np.ones((1024, 1), dtype="float32") * 0.5
        original_id = id(indata)
        worker._audio_callback(indata, 1024, None, None)
        assert id(worker._chunks[0]) != original_id

    def test_callback_rms_silence(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        levels = []
        worker.level_changed.connect(levels.append)
        silent = np.zeros((1024, 1), dtype="float32")
        worker._audio_callback(silent, 1024, None, None)
        assert levels[0] == pytest.approx(0.0)

    def test_callback_rms_clamped_to_one(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        levels = []
        worker.level_changed.connect(levels.append)
        loud = np.ones((1024, 1), dtype="float32")   # maximum amplitude
        worker._audio_callback(loud, 1024, None, None)
        assert levels[0] <= 1.0

    def test_callback_rms_proportional(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        levels = []
        worker.level_changed.connect(levels.append)
        quiet = np.ones((1024, 1), dtype="float32") * 0.1
        worker._audio_callback(quiet, 1024, None, None)
        assert 0.0 < levels[0] < 1.0

    def test_callback_status_emits_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        indata = np.zeros((1024, 1), dtype="float32")
        worker._audio_callback(indata, 1024, None, "input overflow")
        assert any("overflow" in m for m in logs)

    def test_multiple_callbacks_accumulate(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        indata = np.ones((512, 1), dtype="float32")
        for _ in range(4):
            worker._audio_callback(indata, 512, None, None)
        assert len(worker._chunks) == 4

    def test_callback_status_true_logs_warning(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, m)))
        
        class DummyStatus:
            def __bool__(self): return True
            def __str__(self): return "overflow"
            
        mock_status = DummyStatus()
        
        worker._audio_callback(None, 1024, None, mock_status)
        assert any(l == "WRN" and "overflow" in m for l, m in logs)

class TestStopMechanism:
    def test_stop_event_set_on_stop(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        with patch.object(worker, "_close_stream"):
            with patch.object(worker, "wait"):
                worker.stop()
        assert worker._stop_event.is_set()


class TestGracefulDegradation:
    def test_intentional_close_starts_false(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        assert worker._intentional_close is False

    def test_start_recording_resets_intentional_close(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._intentional_close = True
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            worker.start_recording()
        assert worker._intentional_close is False

    def test_start_recording_passes_finished_callback(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            worker.start_recording()
        _, kwargs = mock_cls.call_args
        assert kwargs.get("finished_callback") == worker._on_stream_finished

    def test_close_stream_sets_intentional_close(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._stream = MagicMock()
        worker._close_stream()
        assert worker._intentional_close is True

    def test_close_stream_clears_stream_ref(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._stream = MagicMock()
        worker._close_stream()
        assert worker._stream is None

    def test_on_stream_finished_intentional_emits_nothing(self, qapp, mock_settings):
        """No signals should be emitted on an intentional close."""
        worker = AudioWorker(mock_settings)
        errors, logs, levels = [], [], []
        worker.error_occurred.connect(errors.append)
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        worker.level_changed.connect(levels.append)
        worker._intentional_close = True
        worker._on_stream_finished()
        assert errors == []
        assert not any("disconnected" in m for m in logs)
        assert levels == []

    def test_on_stream_finished_unexpected_emits_error(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        errors = []
        worker.error_occurred.connect(errors.append)
        worker._intentional_close = False
        worker._on_stream_finished()
        assert len(errors) == 1
        assert "disconnected" in errors[0].lower()

    def test_on_stream_finished_unexpected_emits_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        worker._intentional_close = False
        worker._on_stream_finished()
        assert any("connection lost" in m.lower() for m in logs)

    def test_on_stream_finished_unexpected_resets_level_bar(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        levels = []
        worker.level_changed.connect(levels.append)
        worker._intentional_close = False
        worker._on_stream_finished()
        assert 0.0 in levels

    def test_on_stream_finished_unexpected_clears_stream(self, qapp, mock_settings):
        """Zombie state is prevented: _stream must be None."""
        worker = AudioWorker(mock_settings)
        worker._stream = MagicMock()
        worker._intentional_close = False
        worker._on_stream_finished()
        assert worker._stream is None

    def test_stop_recording_after_disconnect_is_noop(self, qapp, mock_settings):
        """After a disconnect, releasing F9 must not emit audio_ready."""
        worker = AudioWorker(mock_settings)
        ready = []
        worker.audio_ready.connect(ready.append)
        worker._stream = None
        worker._chunks.append(np.ones((1024, 1), dtype="float32"))
        worker.stop_recording()
        assert ready == []

    def test_recovery_opens_new_stream_after_disconnect(self, qapp, mock_settings):
        """After a disconnect, the next start_recording call must attempt to open a new stream."""
        worker = AudioWorker(mock_settings)
        worker._stream = None
        worker._intentional_close = False
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            worker.start_recording()
        assert mock_cls.call_count == 1

    def test_double_disconnect_does_not_crash(self, qapp, mock_settings):
        """Calling _on_stream_finished twice (race condition) must not raise."""
        worker = AudioWorker(mock_settings)
        worker._intentional_close = False
        worker._on_stream_finished()
        worker._on_stream_finished()   # _stream is already None, second call is harmless


class TestRun:
    """run() body: log emit + event wait (lines 32-33)."""

    def test_run_returns_when_stop_event_set(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._stop_event.set()
        worker.run()   # must not block


class TestStopRecordingException:
    """np.concatenate exception branch inside stop_recording (lines 104-106)."""

    def _worker_with_chunk(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._stream = MagicMock()
        worker._chunks.append(np.ones((512, 1), dtype="float32"))
        return worker

    def test_concatenate_error_emits_err_log(self, qapp, mock_settings):
        worker = self._worker_with_chunk(qapp, mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        with patch("numpy.concatenate", side_effect=ValueError("shape mismatch")):
            worker.stop_recording()
        assert any(l == "ERR" and "merge error" in m.lower() for l, _, m in logs)

    def test_concatenate_error_emits_error_occurred(self, qapp, mock_settings):
        worker = self._worker_with_chunk(qapp, mock_settings)
        errors = []
        worker.error_occurred.connect(errors.append)
        with patch("numpy.concatenate", side_effect=ValueError("shape mismatch")):
            worker.stop_recording()
        assert any("audio_merge_error" in e for e in errors)


class TestAudioCallbackException:
    """Exception branch inside _audio_callback (lines 120-121)."""

    def test_callback_exception_emits_err_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        indata = np.ones((1024, 1), dtype="float32")
        with patch("numpy.sqrt", side_effect=RuntimeError("math error")):
            worker._audio_callback(indata, 1024, None, None)
        assert any(l == "ERR" and "interrupted" in m.lower() for l, _, m in logs)

    def test_callback_exception_does_not_propagate(self, qapp, mock_settings):
        """The sounddevice callback must not swallow exceptions; otherwise the stream crashes."""
        worker = AudioWorker(mock_settings)
        indata = np.ones((1024, 1), dtype="float32")
        with patch("numpy.sqrt", side_effect=RuntimeError("math error")):
            worker._audio_callback(indata, 1024, None, None)  # must not raise


class TestOnStreamFinishedException:
    """Outer exception branch inside _on_stream_finished (lines 132-133)."""

    def test_inner_exception_emits_err_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        worker._intentional_close = False
        with patch.object(worker, "level_changed") as mock_level:
            mock_level.emit.side_effect = RuntimeError("emit failed")
            worker._on_stream_finished()
        assert any(l == "ERR" and "close error" in m.lower() for l, _, m in logs)

    def test_inner_exception_does_not_propagate(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._intentional_close = False
        with patch.object(worker, "level_changed") as mock_level:
            mock_level.emit.side_effect = RuntimeError("emit failed")
            worker._on_stream_finished()   # must not raise


class TestCloseStreamException:
    """stream.stop/close exception branch inside _close_stream (lines 141-142)."""

    def test_stream_stop_error_emits_wrn_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        mock_stream = MagicMock()
        mock_stream.stop.side_effect = RuntimeError("device busy")
        worker._stream = mock_stream
        worker._close_stream()
        assert any(l == "WRN" and "could not be closed" in m.lower() for l, _, m in logs)

    def test_stream_stop_error_still_clears_stream(self, qapp, mock_settings):
        """finally guarantee after exception: _stream = None."""
        worker = AudioWorker(mock_settings)
        mock_stream = MagicMock()
        mock_stream.stop.side_effect = RuntimeError("device busy")
        worker._stream = mock_stream
        worker._close_stream()
        assert worker._stream is None

    def test_stream_close_error_emits_wrn_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        mock_stream = MagicMock()
        mock_stream.close.side_effect = RuntimeError("close error")
        worker._stream = mock_stream
        worker._close_stream()
        assert any(l == "WRN" and "could not be closed" in m.lower() for l, _, m in logs)

class TestDeviceAvailable:
    def test_device_available_exception_returns_false(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker.set_device(1)
        with patch("sounddevice.query_devices", side_effect=Exception("error")):
            assert worker._device_available() is False


class TestRefreshDevices:
    _MOCK_DEVICES = [
        {"name": "Microphone A", "max_input_channels": 2},
        {"name": "Speaker",      "max_input_channels": 0},   # output-only device, must be filtered
        {"name": "Microphone B", "max_input_channels": 1},
    ]

    def _patch_sd(self, default_input_index: int = 0):
        mock_default = MagicMock()
        mock_default.device = [default_input_index, 0]
        return (
            patch("sounddevice.query_devices", return_value=self._MOCK_DEVICES),
            patch("sounddevice.default", mock_default),
        )

    def test_emits_devices_ready(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        emitted = []
        worker.devices_ready.connect(emitted.append)
        p1, p2 = self._patch_sd()
        with p1, p2:
            worker.refresh_devices()
        assert len(emitted) == 1

    def test_filters_output_only_devices(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        emitted = []
        worker.devices_ready.connect(emitted.append)
        p1, p2 = self._patch_sd()
        with p1, p2:
            worker.refresh_devices()
        assert len(emitted[0]) == 2   # Speaker (max_input=0) filtered out

    def test_marks_default_with_varsayilan(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        emitted = []
        worker.devices_ready.connect(emitted.append)
        p1, p2 = self._patch_sd(default_input_index=0)
        with p1, p2:
            worker.refresh_devices()
        labels = [label for label, _, _ in emitted[0]]
        assert any("(Default)" in lbl for lbl in labels)

    def test_exactly_one_default(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        emitted = []
        worker.devices_ready.connect(emitted.append)
        p1, p2 = self._patch_sd(default_input_index=0)
        with p1, p2:
            worker.refresh_devices()
        defaults = [is_def for _, _, is_def in emitted[0]]
        assert sum(defaults) == 1

    def test_item_tuple_structure(self, qapp, mock_settings):
        """Each item must be in the form (label: str, index: int, is_default: bool)."""
        worker = AudioWorker(mock_settings)
        emitted = []
        worker.devices_ready.connect(emitted.append)
        p1, p2 = self._patch_sd()
        with p1, p2:
            worker.refresh_devices()
        label, index, is_default = emitted[0][0]
        assert isinstance(label, str)
        assert isinstance(index, int)
        assert isinstance(is_default, bool)

    def test_non_input_device_not_in_list(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        emitted = []
        worker.devices_ready.connect(emitted.append)
        p1, p2 = self._patch_sd()
        with p1, p2:
            worker.refresh_devices()
        names = [label for label, _, _ in emitted[0]]
        assert not any("Speaker" in n for n in names)

    def test_error_emits_empty_list(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        emitted = []
        worker.devices_ready.connect(emitted.append)
        with patch("sounddevice.query_devices", side_effect=Exception("hardware error")):
            worker.refresh_devices()
        assert emitted[0] == []

    def test_error_emits_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        with patch("sounddevice.query_devices", side_effect=Exception("hardware error")):
            worker.refresh_devices()
        assert any("could not retrieve" in m.lower() for m in logs)


# Tests for the remaining 10 lines (100% coverage)

class TestResample:
    def test_resample_same_sr(self, mock_settings):
        from workers.audio_worker import _resample
        arr = np.array([1.0, 2.0, 3.0], dtype="float32")
        res = _resample(arr, 16000, 16000)
        assert res is arr
        
    def test_resample_different_sr(self, mock_settings):
        from workers.audio_worker import _resample
        arr = np.array([1.0, 1.0, 1.0], dtype="float32")
        res = _resample(arr, 48000, 16000)
        assert len(res) == 1
        assert res.dtype == np.float32

class TestStartRecordingDeviceUnavailable:
    def test_device_none(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._device_index = None
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.start_recording()
        assert any("osd.mic_no_device" in e for e in errors)
        assert worker._stream is None

    def test_device_not_found(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._device_index = 99
        errors = []
        worker.error_occurred.connect(errors.append)
        with patch.object(worker, "_device_available", return_value=False):
            worker.start_recording()
        assert any("osd.mic_not_found" in e for e in errors)
        assert worker._stream is None

class TestStopRecordingShortDuration:
    def test_skips_short_duration(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._stream = MagicMock()
        # MIN_RECORDING_DURATION is 0.5 seconds. Providing 100 frames (too short)
        worker._chunks.append(np.ones((100, 1), dtype="float32"))
        
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, m)))
        worker.stop_recording()

        assert any(l == "WRN" and "too short" in m.lower() for l, m in logs)

class TestDeviceAvailableBranches:
    def test_returns_false_if_no_input_channels(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker.set_device(1)
        mock_dev = {"max_input_channels": 0}
        with patch("sounddevice.query_devices", return_value=mock_dev):
            assert worker._device_available() is False

class TestAudioCallbackEmpty:
    def test_ignores_none_indata_and_none_status(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._audio_callback(None, 1024, None, None)
        assert len(worker._chunks) == 0



class TestAudioCallbackSilenceTimer:
    def test_silence_timer_starts_on_first_zero_rms(self, qapp, mock_settings):
        """rms==0.0 on first callback: timer is started (line 228)."""
        worker = AudioWorker(mock_settings)
        silent = np.zeros((1024, 1), dtype="float32")
        worker._audio_callback(silent, 1024, None, None)
        assert worker._silence_timer.isValid()

    def test_muted_detected_emitted_after_elapsed(self, qapp, mock_settings):
        """Timer > 1500ms and not yet notified: muted_detected + beep (lines 229-234)."""
        worker = AudioWorker(mock_settings)
        muted = []
        worker.muted_detected.connect(lambda: muted.append(True))

        worker._silence_timer.start()
        # elapsed() is always >= 0; we mock it to return 2000ms
        with patch.object(worker._silence_timer, "isValid", return_value=True), \
             patch.object(worker._silence_timer, "elapsed", return_value=2000), \
             patch("winsound.Beep"):
            silent = np.zeros((1024, 1), dtype="float32")
            worker._audio_callback(silent, 1024, None, None)

        assert len(muted) == 1
        assert worker._silence_notified is True

    def test_muted_detected_not_emitted_twice(self, qapp, mock_settings):
        """If _silence_notified=True, a second callback must not emit again."""
        worker = AudioWorker(mock_settings)
        worker._silence_notified = True
        muted = []
        worker.muted_detected.connect(lambda: muted.append(True))

        with patch.object(worker._silence_timer, "isValid", return_value=True), \
             patch.object(worker._silence_timer, "elapsed", return_value=2000), \
             patch("winsound.Beep"):
            silent = np.zeros((1024, 1), dtype="float32")
            worker._audio_callback(silent, 1024, None, None)

        assert len(muted) == 0
