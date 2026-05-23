"""
AudioWorker testleri.
sounddevice.InputStream mock'lanır; mikrofon gerekmez.
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
            worker.start_recording()   # ikinci çağrı yoksayılmalı

        assert mock_stream_cls.call_count == 1

    def test_start_recording_emits_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream_cls.return_value = MagicMock()
            worker.start_recording()
        assert any("başladı" in m.lower() for m in logs)

    def test_start_recording_emits_error_on_failure(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        errors = []
        worker.error_occurred.connect(errors.append)
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream", side_effect=Exception("cihaz yok")):
            worker.start_recording()
        assert len(errors) == 1
        assert "Mikrofon açılamadı" in errors[0]

    def test_stream_is_none_after_error(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream", side_effect=Exception("hata")):
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
        """paInvalidDevice (-9996): fallback denenmemeli, 'Mikrofon bağlı değil' iletilmeli."""
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

        assert stream_open_count == 1, "Fallback denenmemeli"
        assert errors == ["Mikrofon bağlı değil"]
        assert worker._stream is None

class TestStopRecording:
    def test_stop_recording_when_not_recording_does_nothing(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        worker.stop_recording()   # stream None → erken çıkış
        assert not any("Kayıt tamamlandı" in m for m in logs)

    def test_stop_recording_empty_chunks_no_signal(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        ready = []
        worker.audio_ready.connect(ready.append)

        mock_stream = MagicMock()
        worker._stream = mock_stream
        # _chunks boş bırak
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

        # 1 saniyelik ses: 16000 frame
        chunk = np.ones((SAMPLE_RATE, 1), dtype="float32")
        worker._chunks.append(chunk)

        worker.stop_recording()
        assert any("1.0" in m for m in logs)

    def test_stop_recording_resamples_if_native_sr_different(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._native_sr = 48000
        worker._stream = MagicMock()
        worker._chunks.append(np.ones((24000, 1), dtype="float32")) # 0.5 saniye
        
        ready = []
        worker.audio_ready.connect(ready.append)
        
        mock_settings.set("vad_threshold", 0.0)
        worker.stop_recording()
            
        assert len(ready) == 1
        assert len(ready[0]) == 8000  # 48k'den 16k'ya düşmüş boyut


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
        loud = np.ones((1024, 1), dtype="float32")   # maksimum genlik
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
        """Kasıtlı kapatmada hiçbir sinyal üretilmemeli."""
        worker = AudioWorker(mock_settings)
        errors, logs, levels = [], [], []
        worker.error_occurred.connect(errors.append)
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        worker.level_changed.connect(levels.append)
        worker._intentional_close = True
        worker._on_stream_finished()
        assert errors == []
        assert not any("koptu" in m for m in logs)
        assert levels == []

    def test_on_stream_finished_unexpected_emits_error(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        errors = []
        worker.error_occurred.connect(errors.append)
        worker._intentional_close = False
        worker._on_stream_finished()
        assert len(errors) == 1
        assert "koptu" in errors[0].lower()

    def test_on_stream_finished_unexpected_emits_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        worker._intentional_close = False
        worker._on_stream_finished()
        assert any("koptu" in m for m in logs)

    def test_on_stream_finished_unexpected_resets_level_bar(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        levels = []
        worker.level_changed.connect(levels.append)
        worker._intentional_close = False
        worker._on_stream_finished()
        assert 0.0 in levels

    def test_on_stream_finished_unexpected_clears_stream(self, qapp, mock_settings):
        """Zombi state önlenir: _stream None olmalı."""
        worker = AudioWorker(mock_settings)
        worker._stream = MagicMock()
        worker._intentional_close = False
        worker._on_stream_finished()
        assert worker._stream is None

    def test_stop_recording_after_disconnect_is_noop(self, qapp, mock_settings):
        """Kopma sonrası F9 bırakılınca audio_ready emitlenmemeli."""
        worker = AudioWorker(mock_settings)
        ready = []
        worker.audio_ready.connect(ready.append)
        worker._stream = None
        worker._chunks.append(np.ones((1024, 1), dtype="float32"))
        worker.stop_recording()
        assert ready == []

    def test_recovery_opens_new_stream_after_disconnect(self, qapp, mock_settings):
        """Kopma sonrası bir sonraki start_recording yeni stream açmayı denemeli."""
        worker = AudioWorker(mock_settings)
        worker._stream = None
        worker._intentional_close = False
        with patch.object(worker, "_device_available", return_value=True), \
             patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            worker.start_recording()
        assert mock_cls.call_count == 1

    def test_double_disconnect_does_not_crash(self, qapp, mock_settings):
        """_on_stream_finished iki kez çağrılırsa (race condition) hata vermemeli."""
        worker = AudioWorker(mock_settings)
        worker._intentional_close = False
        worker._on_stream_finished()
        worker._on_stream_finished()   # _stream zaten None, ikinci çağrı zararsız


class TestRun:
    """run() gövdesi: log emit + event bekleme (lines 32-33)."""

    def test_run_emits_ready_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        worker._stop_event.set()   # wait() anında döner
        worker.run()
        from core.settings import STATE_READY
        assert any(l == "OK" and STATE_READY in m for l, _, m in logs)

    def test_run_returns_when_stop_event_set(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._stop_event.set()
        worker.run()   # must not block


class TestStopRecordingException:
    """stop_recording içindeki np.concatenate exception dalı (lines 104-106)."""

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
        assert any(l == "ERR" and "birleştirme" in m for l, _, m in logs)

    def test_concatenate_error_emits_error_occurred(self, qapp, mock_settings):
        worker = self._worker_with_chunk(qapp, mock_settings)
        errors = []
        worker.error_occurred.connect(errors.append)
        with patch("numpy.concatenate", side_effect=ValueError("shape mismatch")):
            worker.stop_recording()
        assert any("birleştirme" in e for e in errors)


class TestAudioCallbackException:
    """_audio_callback içindeki exception dalı (lines 120-121)."""

    def test_callback_exception_emits_err_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        indata = np.ones((1024, 1), dtype="float32")
        with patch("numpy.sqrt", side_effect=RuntimeError("math error")):
            worker._audio_callback(indata, 1024, None, None)
        assert any(l == "ERR" and "akışı kesildi" in m for l, _, m in logs)

    def test_callback_exception_does_not_propagate(self, qapp, mock_settings):
        """sounddevice callback'i exception yutmamalı; aksi hâlde stream çöker."""
        worker = AudioWorker(mock_settings)
        indata = np.ones((1024, 1), dtype="float32")
        with patch("numpy.sqrt", side_effect=RuntimeError("math error")):
            worker._audio_callback(indata, 1024, None, None)  # must not raise


class TestOnStreamFinishedException:
    """_on_stream_finished içindeki dış exception dalı (lines 132-133)."""

    def test_inner_exception_emits_err_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        worker._intentional_close = False
        with patch.object(worker, "level_changed") as mock_level:
            mock_level.emit.side_effect = RuntimeError("emit failed")
            worker._on_stream_finished()
        assert any(l == "ERR" and "kapanma hatası" in m for l, _, m in logs)

    def test_inner_exception_does_not_propagate(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._intentional_close = False
        with patch.object(worker, "level_changed") as mock_level:
            mock_level.emit.side_effect = RuntimeError("emit failed")
            worker._on_stream_finished()   # must not raise


class TestCloseStreamException:
    """_close_stream içindeki stream.stop/close exception dalı (lines 141-142)."""

    def test_stream_stop_error_emits_wrn_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        mock_stream = MagicMock()
        mock_stream.stop.side_effect = RuntimeError("cihaz meşgul")
        worker._stream = mock_stream
        worker._close_stream()
        assert any(l == "WRN" and "kapatılamadı" in m for l, _, m in logs)

    def test_stream_stop_error_still_clears_stream(self, qapp, mock_settings):
        """Exception sonrası finally: _stream = None garantisi."""
        worker = AudioWorker(mock_settings)
        mock_stream = MagicMock()
        mock_stream.stop.side_effect = RuntimeError("cihaz meşgul")
        worker._stream = mock_stream
        worker._close_stream()
        assert worker._stream is None

    def test_stream_close_error_emits_wrn_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        mock_stream = MagicMock()
        mock_stream.close.side_effect = RuntimeError("close hatası")
        worker._stream = mock_stream
        worker._close_stream()
        assert any(l == "WRN" and "kapatılamadı" in m for l, _, m in logs)

class TestDeviceAvailable:
    def test_device_available_exception_returns_false(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker.set_device(1)
        with patch("sounddevice.query_devices", side_effect=Exception("error")):
            assert worker._device_available() is False


class TestRefreshDevices:
    _MOCK_DEVICES = [
        {"name": "Mikrofon A", "max_input_channels": 2},
        {"name": "Hoparlör",   "max_input_channels": 0},   # çıkış cihazı, filtrelenmeli
        {"name": "Mikrofon B", "max_input_channels": 1},
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
        assert len(emitted[0]) == 2   # Hoparlör (max_input=0) filtrelendi

    def test_marks_default_with_varsayilan(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        emitted = []
        worker.devices_ready.connect(emitted.append)
        p1, p2 = self._patch_sd(default_input_index=0)
        with p1, p2:
            worker.refresh_devices()
        labels = [label for label, _, _ in emitted[0]]
        assert any("(Varsayılan)" in lbl for lbl in labels)

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
        """Her öğe (label: str, index: int, is_default: bool) formunda olmalı."""
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
        assert not any("Hoparlör" in n for n in names)

    def test_error_emits_empty_list(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        emitted = []
        worker.devices_ready.connect(emitted.append)
        with patch("sounddevice.query_devices", side_effect=Exception("donanım hatası")):
            worker.refresh_devices()
        assert emitted[0] == []

    def test_error_emits_log(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        with patch("sounddevice.query_devices", side_effect=Exception("donanım hatası")):
            worker.refresh_devices()
        assert any("alınamadı" in m for m in logs)


# ── EKSİK KALAN 10 SATIRIN (%100 KAPSAM) TESTLERİ ─────────────────────────────

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
        assert any("seçili değil" in e for e in errors)
        assert worker._stream is None

    def test_device_not_found(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._device_index = 99
        errors = []
        worker.error_occurred.connect(errors.append)
        with patch.object(worker, "_device_available", return_value=False):
            worker.start_recording()
        assert any("bulunamadı" in e for e in errors)
        assert worker._stream is None

class TestStopRecordingShortDuration:
    def test_skips_short_duration(self, qapp, mock_settings):
        worker = AudioWorker(mock_settings)
        worker._stream = MagicMock()
        # MIN_RECORDING_DURATION 0.5 saniye. 100 frame veriyoruz (çok kısa)
        worker._chunks.append(np.ones((100, 1), dtype="float32"))
        
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, m)))
        worker.stop_recording()
        
        assert any(l == "WRN" and "çok kısa" in m for l, m in logs)

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
        """rms==0.0 ilk callback: timer başlatılır (satır 228)."""
        worker = AudioWorker(mock_settings)
        silent = np.zeros((1024, 1), dtype="float32")
        worker._audio_callback(silent, 1024, None, None)
        assert worker._silence_timer.isValid()

    def test_muted_detected_emitted_after_elapsed(self, qapp, mock_settings):
        """Timer > 1500ms ve henüz bildirilmemişse muted_detected + beep (satır 229-234)."""
        worker = AudioWorker(mock_settings)
        muted = []
        worker.muted_detected.connect(lambda: muted.append(True))

        worker._silence_timer.start()
        # elapsed() her zaman >= 0; Mock ile 2000ms döndürüyoruz
        with patch.object(worker._silence_timer, "isValid", return_value=True), \
             patch.object(worker._silence_timer, "elapsed", return_value=2000), \
             patch("winsound.Beep"):
            silent = np.zeros((1024, 1), dtype="float32")
            worker._audio_callback(silent, 1024, None, None)

        assert len(muted) == 1
        assert worker._silence_notified is True

    def test_muted_detected_not_emitted_twice(self, qapp, mock_settings):
        """_silence_notified=True ise ikinci callback tekrar emit etmemeli."""
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
