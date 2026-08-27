"""
TranscriptionWorker business logic tests: check_model_exists, reload_model,
_load_model, _transcribe. WhisperInferenceModule is mocked; no real server is started.
"""
import numpy as np
import pytest
from typing import cast
from unittest.mock import patch, MagicMock
from workers.transcription_worker import (
    TranscriptionWorker,
    QUEUE_MAXSIZE,
    _RELOAD,
    _ReloadCommand,
)
from core.settings import MSG_MODEL_NOT_FOUND

AUDIO = np.zeros(1600, dtype="float32")

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

def _make_worker_with_model(qapp, mock_settings, text_to_return: str | None = None) -> TranscriptionWorker:
    """Returns a worker ready with a mock _inference."""
    worker = TranscriptionWorker(mock_settings, MagicMock())
    worker.is_ready = True
    worker._current_model_dir = "/fake/dir"
    if text_to_return is None:
        text_to_return = "Hello world"
    worker._inference = MagicMock()
    worker._inference.transcribe.return_value = text_to_return
    return worker

# check_model_exists
class TestCheckModelExists:
    def test_returns_false_when_no_current_dir(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        assert worker.check_model_exists() is False

    def test_returns_false_when_dir_not_on_filesystem(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._current_model_dir = "/nonexistent/path/xyz"
        assert worker.check_model_exists() is False

    def test_returns_true_when_dir_exists(self, qapp, tmp_path, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._current_model_dir = str(tmp_path)
        assert worker.check_model_exists() is True

    def test_does_not_mutate_is_ready_when_dir_missing(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker.is_ready = True
        worker.check_model_exists()
        assert worker.is_ready is True

    def test_emits_error_occurred_when_dir_missing(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.check_model_exists()
        assert len(errors) == 1

# add_audio → check_model_exists False
class TestAddAudioMissingModel:
    def test_queue_stays_empty_when_not_ready(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())  # is_ready = False
        worker.add_audio(AUDIO)
        assert worker._queue.qsize() == 0

    def test_add_audio_emits_no_error_when_not_ready(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())  # is_ready = False
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.add_audio(AUDIO)
        assert errors == []

# stop
class TestStop:
    def test_puts_poison_pill_in_queue(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker.stop()
        assert worker._queue.get_nowait() is None

    def test_drains_queue_before_poison_pill(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        for _ in range(3):
            worker._queue.put_nowait(AUDIO)
        worker.stop()
        assert worker._queue.get_nowait() is None
        assert worker._queue.empty()

# add_audio: full queue
class TestAddAudioFullQueue:
    def test_full_queue_emits_warning_log(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker.is_ready = True
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, m)))
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.add_audio(AUDIO)
        assert any(lvl == "WRN" for lvl, m in logs)

# reload_model
class TestReloadModel:
    def test_puts_reload_sentinel_in_queue(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker.reload_model()
        assert isinstance(worker._queue.get_nowait(), _ReloadCommand)

# _load_model: no valid dir
class TestLoadModelNoValidDir:
    def _run(self, qapp, mock_settings) -> tuple[TranscriptionWorker, dict]:
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with patch.object(worker.model_provider, "get_active_model_path", return_value=None):
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

# _load_model: success
class TestLoadModelSuccess:
    def _run(self, qapp, mock_settings) -> tuple[TranscriptionWorker, dict, MagicMock]:
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker.model_provider.base_download_dir = "/fake/base"
        worker._inference = MagicMock()
        s = _capture(worker)
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch("pathlib.Path.exists", return_value=True):
            worker._load_model()
        return worker, s, worker._inference

    def test_sets_is_ready_true(self, qapp, mock_settings):
        worker, _, _ = self._run(qapp, mock_settings)
        assert worker.is_ready is True

    def test_sets_current_model_dir(self, qapp, mock_settings):
        worker, _, _ = self._run(qapp, mock_settings)
        assert worker._current_model_dir == "/fake/dir"

    def test_emits_status_ready(self, qapp, mock_settings):
        _, s, _ = self._run(qapp, mock_settings)
        texts = [t for t, _ in s["status"]]
        from core.settings import STATE_READY
        assert any(STATE_READY in t for t in texts)

    def test_loading_state_sequence_true_then_false(self, qapp, mock_settings):
        _, s, _ = self._run(qapp, mock_settings)
        assert s["loading"] == [True, False]

    def test_calls_start_server(self, qapp, mock_settings):
        worker, _, mock_instance = self._run(qapp, mock_settings)
        import os
        from pathlib import Path
        expected_exe = os.path.normpath(str(Path(worker.model_provider.base_download_dir).parent / "bin" / "whisper-server.exe"))
        actual_call_args = mock_instance.start_server.call_args[0]
        assert actual_call_args[0] == "/fake/dir"
        assert os.path.normpath(actual_call_args[1]) == expected_exe

# _load_model: failure
class TestLoadModelFailure:
    def _run(self, qapp, mock_settings, exc=Exception("server crashed")) -> tuple[TranscriptionWorker, dict]:
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._inference = MagicMock()
        worker._inference.start_server.side_effect = exc
        s = _capture(worker)
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch("pathlib.Path.exists", return_value=True):
            worker._load_model()
        return worker, s

    def test_is_ready_stays_false(self, qapp, mock_settings):
        worker, _ = self._run(qapp, mock_settings)
        assert worker.is_ready is False

    def test_emits_error_occurred(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert len(s["errors"]) == 1

# _transcribe: inference None
class TestTranscribeInferenceNone:
    def test_emits_err_log(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._inference = None
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(l))
        worker._transcribe(AUDIO)
        assert "ERR" in logs

# _transcribe: success
class TestTranscribeSuccess:
    def _run(self, qapp, mock_settings, text_to_return="test word") -> tuple[TranscriptionWorker, dict]:
        worker = _make_worker_with_model(qapp, mock_settings, text_to_return)
        s = _capture(worker)
        worker._transcribe(AUDIO)
        return worker, s

    def test_emits_text_ready(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert len(s["text"]) == 1
        assert "test word" in s["text"][0]

    def test_calls_inference_transcribe(self, qapp, mock_settings):
        worker, _ = self._run(qapp, mock_settings)
        worker._inference.transcribe.assert_called_once()
        args, _ = worker._inference.transcribe.call_args
        assert args[0] is AUDIO

# _transcribe: empty result
class TestTranscribeEmptyResult:
    def _run_empty(self, qapp, mock_settings, text_to_return) -> dict:
        worker = _make_worker_with_model(qapp, mock_settings, text_to_return)
        s = _capture(worker)
        worker._transcribe(AUDIO)
        return s

    def test_empty_string_emits_wrn_log(self, qapp, mock_settings):
        s = self._run_empty(qapp, mock_settings, "")
        assert any(lvl == "WRN" for lvl, _, _ in s["logs"])

    def test_empty_string_no_text_ready(self, qapp, mock_settings):
        s = self._run_empty(qapp, mock_settings, "")
        assert s["text"] == []

# _transcribe: exception
class TestTranscribeException:
    def _run_with_error(self, qapp, mock_settings, exc=Exception("transcription error")) -> dict:
        worker = _make_worker_with_model(qapp, mock_settings)
        cast(MagicMock, worker._inference).transcribe.side_effect = exc
        s = _capture(worker)
        worker._transcribe(AUDIO)
        return s

    def test_emits_error_occurred(self, qapp, mock_settings):
        s = self._run_with_error(qapp, mock_settings)
        assert len(s["errors"]) == 1

class TestRunLoop:
    def test_run_dispatches_audio_to_transcribe(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        audio = np.zeros(16000, dtype="float32")
        worker._queue.put(audio)
        worker._queue.put(None)
        with patch.object(worker, "_load_model"), \
             patch.object(worker, "_transcribe") as mock_transcribe, \
             patch.object(worker, "_stop_server"):
            worker.run()
        mock_transcribe.assert_called_once_with(audio)
