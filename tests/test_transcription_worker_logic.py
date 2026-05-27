"""
TranscriptionWorker business logic tests: check_model_exists, reload_model,
_load_model, _transcribe. WhisperModel is mocked; no real model file is needed.
"""
import numpy as np
import pytest
from typing import cast
from unittest.mock import patch, MagicMock
from workers.transcription_worker import (
    TranscriptionWorker,
    QUEUE_MAXSIZE,
    DEVICE,
    _RELOAD,
    _ReloadCommand,
)
from core.settings import MSG_MODEL_NOT_FOUND

AUDIO = np.zeros(1600, dtype="float32")


import sys
sys.modules['faster_whisper'] = MagicMock()

_PATCH_MODEL_CLS = "faster_whisper.WhisperModel"


def _capture(worker: TranscriptionWorker) -> dict:
    s: dict = {"logs": [], "errors": [], "status": [], "loading": [], "text": [],
               "missing": [], "loaded": []}
    worker.log_entry.connect(lambda l, c, m: s["logs"].append((l, c, m)))
    worker.error_occurred.connect(s["errors"].append)
    worker.status_changed.connect(lambda t, c: s["status"].append((t, c)))
    worker.loading_state_changed.connect(s["loading"].append)
    worker.text_ready.connect(s["text"].append)
    worker.model_missing.connect(lambda: s["missing"].append(True))
    worker.model_loaded.connect(lambda: s["loaded"].append(True))
    return s


def _make_worker_with_model(qapp, mock_settings, segments_text: list[str] | None = None) -> TranscriptionWorker:
    """Returns a worker ready with a mock _model."""
    worker = TranscriptionWorker(mock_settings)
    if segments_text is None:
        segments_text = [" Hello world"]
    worker._model = MagicMock()
    segs = [MagicMock(text=t) for t in segments_text]
    worker._model.transcribe.return_value = (segs, MagicMock())
    return worker


# check_model_exists

class TestCheckModelExists:

    def test_returns_false_when_no_current_dir(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        assert worker.check_model_exists() is False

    def test_returns_false_when_dir_not_on_filesystem(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker._current_model_dir = "/nonexistent/path/xyz"
        assert worker.check_model_exists() is False

    def test_returns_true_when_dir_exists(self, qapp, tmp_path, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker._current_model_dir = str(tmp_path)
        assert worker.check_model_exists() is True

    def test_does_not_mutate_is_ready_when_dir_missing(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker.is_ready = True
        worker.check_model_exists()
        assert worker.is_ready is True

    def test_does_not_change_is_ready_when_dir_exists(self, qapp, tmp_path, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker._current_model_dir = str(tmp_path)
        worker.is_ready = True
        worker.check_model_exists()
        assert worker.is_ready is True

    def test_emits_error_occurred_when_dir_missing(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.check_model_exists()
        assert len(errors) == 1

    def test_emits_err_log_when_dir_missing(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(l))
        worker.check_model_exists()
        assert "ERR" in logs

    def test_emits_status_changed_when_dir_missing(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        statuses = []
        worker.status_changed.connect(lambda t, c: statuses.append((t, c)))
        worker.check_model_exists()
        assert statuses

    def test_no_signals_when_dir_exists(self, qapp, tmp_path, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker._current_model_dir = str(tmp_path)
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.check_model_exists()
        assert errors == []


# add_audio → check_model_exists False

class TestAddAudioMissingModel:

    def test_queue_stays_empty_when_not_ready(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)  # is_ready = False
        worker.add_audio(AUDIO)
        assert worker._queue.qsize() == 0

    def test_add_audio_emits_no_error_when_not_ready(self, qapp, mock_settings):
        """If the model is missing, _load_model already emitted a signal; add_audio should return silently."""
        worker = TranscriptionWorker(mock_settings)  # is_ready = False
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.add_audio(AUDIO)
        assert errors == []

    def test_add_audio_emits_no_status_when_not_ready(self, qapp, mock_settings):
        """If the model is missing, add_audio should not emit status_changed — _load_model already did."""
        worker = TranscriptionWorker(mock_settings)  # is_ready = False
        statuses = []
        worker.status_changed.connect(lambda t, c: statuses.append((t, c)))
        worker.add_audio(AUDIO)
        assert statuses == []


# stop

class TestStop:

    def test_puts_poison_pill_in_queue(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker.stop()
        assert worker._queue.get_nowait() is None

    def test_drains_queue_before_poison_pill(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        for _ in range(3):
            worker._queue.put_nowait(AUDIO)
        worker.stop()
        assert worker._queue.get_nowait() is None
        assert worker._queue.empty()


# add_audio: full queue

class TestAddAudioFullQueue:

    def test_full_queue_emits_warning_log(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker.is_ready = True
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, m)))
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.add_audio(AUDIO)
        assert any(lvl == "WRN" for lvl, m in logs)

    def test_full_queue_emits_error_occurred(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker.is_ready = True
        errors = []
        worker.error_occurred.connect(errors.append)
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.add_audio(AUDIO)
        assert len(errors) == 1


# reload_model

class TestReloadModel:

    def test_puts_reload_sentinel_in_queue(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker.reload_model()
        assert isinstance(worker._queue.get_nowait(), _ReloadCommand)

    def test_full_queue_emits_warning_log(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, m)))
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.reload_model()
        assert any(lvl == "WRN" for lvl, m in logs)

    def test_full_queue_does_not_raise(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.reload_model()   # should not raise an exception

    def test_full_queue_does_not_change_queue_size(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.reload_model()
        assert worker._queue.qsize() == QUEUE_MAXSIZE


# _load_model: no valid dir

class TestLoadModelNoValidDir:

    def _run(self, qapp, mock_settings) -> tuple[TranscriptionWorker, dict]:
        worker = TranscriptionWorker(mock_settings)
        s = _capture(worker)
        with patch.object(mock_settings, "get_resolved_model_dir", return_value=None):
            worker._load_model()
        return worker, s

    def test_is_ready_stays_false(self, qapp, mock_settings):
        worker, _ = self._run(qapp, mock_settings)
        assert worker.is_ready is False

    def test_emits_status_not_selected(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        texts = [t for t, _ in s["status"]]
        assert any(MSG_MODEL_NOT_FOUND in t for t in texts)

    def test_emits_model_missing(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert s["missing"] == [True]

    def test_no_loading_spinner(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert s["loading"] == []

    def test_whispermodel_not_instantiated(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        with patch.object(mock_settings, "get_resolved_model_dir", return_value=None), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            worker._load_model()
        mock_cls.assert_not_called()


# _load_model: success

class TestLoadModelSuccess:

    def _run(self, qapp, mock_settings) -> tuple[TranscriptionWorker, dict]:
        worker = TranscriptionWorker(mock_settings)
        s = _capture(worker)
        with patch.object(mock_settings, "get_resolved_model_dir", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS):
            worker._load_model()
        return worker, s

    def test_sets_is_ready_true(self, qapp, mock_settings):
        worker, _ = self._run(qapp, mock_settings)
        assert worker.is_ready is True

    def test_sets_current_model_dir(self, qapp, mock_settings):
        worker, _ = self._run(qapp, mock_settings)
        assert worker._current_model_dir == "/fake/dir"

    def test_emits_ok_log(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert any(lvl == "OK" for lvl, _, _ in s["logs"])

    def test_emits_status_ready(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        texts = [t for t, _ in s["status"]]
        from core.settings import STATE_READY
        assert any(STATE_READY in t for t in texts)

    def test_loading_state_sequence_true_then_false(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert s["loading"] == [True, False]

    def test_no_error_signals(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert s["errors"] == []

    def test_local_files_only_is_always_true(self, qapp, mock_settings):
        """local_files_only=True invariant; this must never be broken."""
        worker = TranscriptionWorker(mock_settings)
        with patch.object(mock_settings, "get_resolved_model_dir", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            worker._load_model()
        _, kwargs = mock_cls.call_args
        assert kwargs.get("local_files_only") is True

    def test_device_is_cpu(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        with patch.object(mock_settings, "get_resolved_model_dir", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            worker._load_model()
        _, kwargs = mock_cls.call_args
        assert kwargs.get("device") == "cpu"

    def test_compute_type_matches_constant(self, qapp, mock_settings):
        mock_settings.set("compute_type", "int8")
        worker = TranscriptionWorker(mock_settings)
        with patch.object(mock_settings, "get_resolved_model_dir", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            worker._load_model()
        _, kwargs = mock_cls.call_args
        assert kwargs.get("compute_type") == "int8"

    def test_emits_model_loaded(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert s["loaded"] == [True]

    def test_does_not_emit_model_missing(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert s["missing"] == []

    def test_deletes_old_model_and_runs_gc(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker._model = MagicMock()
        with patch.object(mock_settings, "get_resolved_model_dir", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS), \
             patch("gc.collect") as mock_gc:
            worker._load_model()
        mock_gc.assert_called_once()
        assert worker._model is not None


# _load_model: failure

class TestLoadModelFailure:

    def _run(self, qapp, mock_settings, exc=Exception("model corrupted")) -> tuple[TranscriptionWorker, dict]:
        worker = TranscriptionWorker(mock_settings)
        s = _capture(worker)
        with patch.object(mock_settings, "get_resolved_model_dir", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS, side_effect=exc):
            worker._load_model()
        return worker, s

    def test_is_ready_stays_false(self, qapp, mock_settings):
        worker, _ = self._run(qapp, mock_settings)
        assert worker.is_ready is False

    def test_current_model_dir_not_set(self, qapp, mock_settings):
        worker, _ = self._run(qapp, mock_settings)
        assert worker._current_model_dir is None

    def test_emits_error_occurred(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert len(s["errors"]) == 1

    def test_error_message_contains_exception_text(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings, exc=Exception("model corrupted"))
        assert "osd.model_load_failed" in s["errors"][0]

    def test_emits_err_log(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert any(lvl == "ERR" for lvl, _, _ in s["logs"])

    def test_emits_status_model_error(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        texts = [t for t, _ in s["status"]]
        assert any("status.model_error" in t for t in texts)

    def test_loading_state_sequence_true_then_false(self, qapp, mock_settings):
        """Even if an error occurs after loading starts, the spinner must be closed."""
        _, s = self._run(qapp, mock_settings)
        assert s["loading"] == [True, False]

    def test_err_log_contains_exception_detail(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings, exc=Exception("model corrupted"))
        err_msgs = [m for lvl, _, m in s["logs"] if lvl == "ERR"]
        assert any("model corrupted" in m for m in err_msgs)


# _load_model: fallback logging

class TestLoadModelFallbackLogging:

    def test_wrn_log_when_fallback_used(self, qapp, mock_settings):
        mock_settings.set("model_dir", "/selected/folder")
        worker = TranscriptionWorker(mock_settings)
        s = _capture(worker)
        with patch.object(mock_settings, "get_resolved_model_dir", return_value="/different/folder"), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            worker._load_model()
        wrn_msgs = [m for lvl, _, m in s["logs"] if lvl == "WRN"]
        assert any("invalid" in m for m in wrn_msgs)

    def test_no_wrn_log_when_dir_unchanged(self, qapp, mock_settings):
        mock_settings.set("model_dir", "/correct/folder")
        worker = TranscriptionWorker(mock_settings)
        s = _capture(worker)
        with patch.object(mock_settings, "get_resolved_model_dir", return_value="/correct/folder"), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            worker._load_model()
        wrn_msgs = [m for lvl, _, m in s["logs"] if lvl == "WRN"]
        assert not any("invalid" in m for m in wrn_msgs)


# _transcribe: model None

class TestTranscribeModelNone:

    def test_emits_err_log(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)  # _model = None
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(l))
        worker._transcribe(AUDIO)
        assert "ERR" in logs

    def test_no_text_ready(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        texts = []
        worker.text_ready.connect(texts.append)
        worker._transcribe(AUDIO)
        assert texts == []


# _transcribe: success

class TestTranscribeSuccess:

    def _run(self, qapp, mock_settings, segments_text=None) -> tuple[TranscriptionWorker, dict]:
        worker = _make_worker_with_model(qapp, mock_settings, segments_text)
        s = _capture(worker)
        worker._transcribe(AUDIO)
        return worker, s

    def test_emits_text_ready(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert len(s["text"]) == 1

    def test_output_is_stripped(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings, segments_text=["  hello  "])
        assert s["text"][0] == "hello"

    def test_emits_ok_log(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert any(lvl == "OK" for lvl, _, _ in s["logs"])

    def test_log_contains_transcribed_text(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings, segments_text=[" test word"])
        messages = [m for _, _, m in s["logs"]]
        assert any("test word" in m for m in messages)

    def test_multiple_segments_concatenated(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings, segments_text=["first", " second", " third"])
        assert "first" in s["text"][0]
        assert "second" in s["text"][0]

    def test_no_error_signals(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert s["errors"] == []


# _transcribe: empty transcription

class TestTranscribeEmptyResult:

    def _run_empty(self, qapp, mock_settings, segments_text) -> dict:
        worker = _make_worker_with_model(qapp, mock_settings, segments_text)
        s = _capture(worker)
        worker._transcribe(AUDIO)
        return s

    def test_empty_segments_emits_wrn_log(self, qapp, mock_settings):
        s = self._run_empty(qapp, mock_settings, [])
        assert any(lvl == "WRN" for lvl, _, _ in s["logs"])

    def test_empty_segments_no_text_ready(self, qapp, mock_settings):
        s = self._run_empty(qapp, mock_settings, [])
        assert s["text"] == []

    def test_whitespace_only_segments_no_text_ready(self, qapp, mock_settings):
        s = self._run_empty(qapp, mock_settings, ["   ", "  "])
        assert s["text"] == []

    def test_whitespace_only_emits_wrn_log(self, qapp, mock_settings):
        s = self._run_empty(qapp, mock_settings, ["   "])
        assert any(lvl == "WRN" for lvl, _, _ in s["logs"])


# _transcribe: hallucination

class TestTranscribeHallucination:

    def _run_hallucination(self, qapp, mock_settings, segments_text) -> dict:
        worker = _make_worker_with_model(qapp, mock_settings, segments_text)
        s = _capture(worker)
        worker._transcribe(AUDIO)
        return s

    @pytest.mark.parametrize("text", [
        "Sessiz.",
        "Altyazı",
        "Müzik.",
        " İzlediğiniz için teşekkürler! ",
        "Çeviri,"
    ])
    def test_filters_known_hallucinations(self, qapp, mock_settings, text):
        s = self._run_hallucination(qapp, mock_settings, [text])
        assert s["text"] == []  # Output should be suppressed
        assert any(lvl == "WRN" for lvl, _, m in s["logs"])


# _transcribe: exception

class TestTranscribeException:

    def _run_with_error(self, qapp, mock_settings, exc=Exception("transcription error")) -> dict:
        worker = _make_worker_with_model(qapp, mock_settings)
        cast(MagicMock, worker._model).transcribe.side_effect = exc
        s = _capture(worker)
        worker._transcribe(AUDIO)
        return s

    def test_emits_error_occurred(self, qapp, mock_settings):
        s = self._run_with_error(qapp, mock_settings)
        assert len(s["errors"]) == 1

    def test_error_message_contains_exception_text(self, qapp, mock_settings):
        s = self._run_with_error(qapp, mock_settings, exc=Exception("transcription error"))
        assert "osd.stt_error" in s["errors"][0]

    def test_emits_err_log(self, qapp, mock_settings):
        s = self._run_with_error(qapp, mock_settings)
        assert any(lvl == "ERR" for lvl, _, _ in s["logs"])

    def test_no_text_ready_on_exception(self, qapp, mock_settings):
        s = self._run_with_error(qapp, mock_settings)
        assert s["text"] == []


class TestRunLoop:
    """run() body (lines 42-55): queue is pre-filled and called synchronously."""

    def test_run_calls_load_model_on_start(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker._queue.put(None)
        with patch.object(worker, "_load_model") as mock_load:
            worker.run()
        mock_load.assert_called_once()

    def test_run_poison_pill_exits_loop(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker._queue.put(None)
        with patch.object(worker, "_load_model"):
            worker.run()  # must return, not block

    def test_run_dispatches_audio_to_transcribe(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        audio = np.zeros(16000, dtype="float32")
        worker._queue.put(audio)
        worker._queue.put(None)
        with patch.object(worker, "_load_model"), \
             patch.object(worker, "_transcribe") as mock_transcribe:
            worker.run()
        mock_transcribe.assert_called_once_with(audio)

    def test_run_reload_calls_load_model_again(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        worker._queue.put(_RELOAD)
        worker._queue.put(None)
        with patch.object(worker, "_load_model") as mock_load:
            worker.run()
        assert mock_load.call_count == 2  # start + _RELOAD

    def test_run_multiple_audio_chunks(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings)
        for _ in range(3):
            worker._queue.put(np.zeros(8000, dtype="float32"))
        worker._queue.put(None)
        transcribed = []
        with patch.object(worker, "_load_model"), \
             patch.object(worker, "_transcribe", side_effect=transcribed.append):
            worker.run()
        assert len(transcribed) == 3

    def test_run_unexpected_exception_emits_error(self, qapp, mock_settings):
        """If _transcribe raises an unexpected exception, error_occurred should be emitted."""
        worker = TranscriptionWorker(mock_settings)
        worker._queue.put(np.zeros(8000, dtype="float32"))
        worker._queue.put(None)
        s = _capture(worker)
        with patch.object(worker, "_load_model"), \
             patch.object(worker, "_transcribe", side_effect=MemoryError("RAM full")):
            worker.run()
        assert len(s["errors"]) >= 1

    def test_run_unexpected_exception_emits_err_log(self, qapp, mock_settings):
        """If _transcribe raises an unexpected exception, an ERR log should be written."""
        worker = TranscriptionWorker(mock_settings)
        worker._queue.put(np.zeros(8000, dtype="float32"))
        worker._queue.put(None)
        s = _capture(worker)
        with patch.object(worker, "_load_model"), \
             patch.object(worker, "_transcribe", side_effect=MemoryError("RAM full")):
            worker.run()
        assert any(lvl == "ERR" for lvl, _, _ in s["logs"])
