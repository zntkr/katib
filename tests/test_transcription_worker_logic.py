"""
TranscriptionWorker business logic tests: reload_model,
_load_model, _transcribe. WhisperModel is mocked; no real model file is needed.
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
from core.settings import MSG_MODEL_NOT_FOUND, STATE_LOADING, STATE_READY

AUDIO = np.zeros(1600, dtype="float32")


import sys
from tests.log_helpers import on_log_entry
sys.modules['faster_whisper'] = MagicMock()

_PATCH_MODEL_CLS = "faster_whisper.WhisperModel"


def _capture(worker: TranscriptionWorker) -> dict:
    s: dict = {"logs": [], "errors": [], "status": [], "loading": [], "text": [],
               "missing": [], "loaded": []}
    on_log_entry(lambda l, c, m: s["logs"].append((l, c, m)))
    worker.error_occurred.connect(s["errors"].append)
    worker.status_changed.connect(lambda t, c: s["status"].append((t, c)))
    worker.loading_state_changed.connect(s["loading"].append)
    worker.text_ready.connect(s["text"].append)
    worker.model_missing.connect(lambda: s["missing"].append(True))
    worker.model_loaded.connect(lambda: s["loaded"].append(True))
    return s


def _make_worker_with_model(qapp, mock_settings, segments_text: list[str] | None = None) -> TranscriptionWorker:
    """Returns a worker ready with a mock _model."""
    worker = TranscriptionWorker(mock_settings, MagicMock())
    if segments_text is None:
        segments_text = [" Hello world"]
    worker._model = MagicMock()
    segs = [MagicMock(text=t) for t in segments_text]
    worker._model.transcribe.return_value = (segs, MagicMock())
    return worker


# add_audio while the model is not ready

class TestAddAudioMissingModel:

    def test_queue_stays_empty_when_not_ready(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())  # is_ready = False
        worker.add_audio(AUDIO)
        assert worker._queue.qsize() == 0

    def test_add_audio_while_loading_reports_loading(self, qapp, mock_settings):
        """Audio dropped because a (re)load is running must be reported, or the OSD stays on 'Listening'."""
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker.is_loading = True
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.add_audio(AUDIO)
        assert errors == [STATE_LOADING]

    def test_add_audio_without_model_reports_missing_model(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker.is_loading = False
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.add_audio(AUDIO)
        assert errors == [MSG_MODEL_NOT_FOUND]

    def test_add_audio_emits_no_status_when_not_ready(self, qapp, mock_settings):
        """add_audio should not emit status_changed — _load_model already did."""
        worker = TranscriptionWorker(mock_settings, MagicMock())  # is_ready = False
        statuses = []
        worker.status_changed.connect(lambda t, c: statuses.append((t, c)))
        worker.add_audio(AUDIO)
        assert statuses == []


class TestIsLoading:
    """is_loading separates 'model is loading' from 'no model' for the UI."""

    def test_loading_until_first_load_finishes(self, qapp, mock_settings):
        assert TranscriptionWorker(mock_settings, MagicMock()).is_loading is True

    def test_true_while_model_loads(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        seen = []
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS, side_effect=lambda *a, **k: seen.append(worker.is_loading)):
            worker._load_model()
        assert seen == [True]

    @pytest.mark.parametrize("model_path, side_effect", [
        ("/fake/dir", None),                 # success
        ("/fake/dir", Exception("corrupt")), # failure
        (None, None),                        # no model
    ])
    def test_false_after_load_attempt(self, qapp, mock_settings, model_path, side_effect):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        with patch.object(worker.model_provider, "get_active_model_path", return_value=model_path), \
             patch(_PATCH_MODEL_CLS, side_effect=side_effect):
            worker._load_model()
        assert worker.is_loading is False


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
        on_log_entry(lambda l, c, m: logs.append((l, m)))
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.add_audio(AUDIO)
        assert any(lvl == "WRN" for lvl, m in logs)

    def test_full_queue_emits_error_occurred(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
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
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker.reload_model()
        assert isinstance(worker._queue.get_nowait(), _ReloadCommand)

    def test_full_queue_emits_warning_log(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        logs = []
        on_log_entry(lambda l, c, m: logs.append((l, m)))
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.reload_model()
        assert any(lvl == "WRN" for lvl, m in logs)

    def test_full_queue_does_not_raise(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.reload_model()   # should not raise an exception

    def test_full_queue_does_not_change_queue_size(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        for _ in range(QUEUE_MAXSIZE):
            worker._queue.put_nowait(AUDIO)
        worker.reload_model()
        assert worker._queue.qsize() == QUEUE_MAXSIZE


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

    def test_no_loading_spinner(self, qapp, mock_settings):
        _, s = self._run(qapp, mock_settings)
        assert s["loading"] == []

    def test_whispermodel_not_instantiated(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        with patch.object(worker.model_provider, "get_active_model_path", return_value=None), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            worker._load_model()
        mock_cls.assert_not_called()


# _transcribe passes the clip length to the hallucination filter

class TestTranscribeFilterDuration:

    def _texts(self, qapp, mock_settings, seconds, segment):
        worker = _make_worker_with_model(qapp, mock_settings, [segment])
        texts = []
        worker.text_ready.connect(texts.append)
        worker._transcribe(np.zeros(int(16000 * seconds), dtype=np.float32))
        return texts

    def test_stock_phrase_from_a_short_clip_is_dropped(self, qapp, mock_settings):
        assert self._texts(qapp, mock_settings, 1.0, " İzlediğiniz için teşekkürler.") == []

    def test_stock_phrase_from_a_long_clip_is_kept(self, qapp, mock_settings):
        assert self._texts(qapp, mock_settings, 10.0, " İzlediğiniz için teşekkürler.") == ["İzlediğiniz için teşekkürler."]


# Pieces transcribed while the user is still speaking (plan 0014)

SR = 16000
_CHUNKS = "workers.transcription_worker.speech_chunks"


def _speech(start_s: float, end_s: float) -> dict:
    return {"start": int(start_s * SR), "end": int(end_s * SR)}


class TestShortPiecesOnTheGpu:
    """A separate piece costs one more encoder pass: seconds on a CPU, a few hundred ms on a
    GPU. Hands-free on the GPU a sentence is therefore typed at its first real pause, not only
    after 8 s of speech (which left every short dictation waiting for the second tap)."""
    SNAPSHOT = np.zeros(4 * SR, dtype=np.float32)   # the recording so far: 4 s

    def _partial(self, qapp, mock_settings, device: str, hands_free: bool, speech_until: float = 2.5):
        worker = _make_worker_with_model(qapp, mock_settings, [" Kısa cümle."])
        worker._device, worker.hands_free = device, hands_free
        s = _capture(worker)
        with patch(_CHUNKS, return_value=[_speech(0, speech_until)]):
            worker._transcribe_partial(self.SNAPSHOT)
        return worker, s

    def test_hands_free_on_the_gpu_a_short_sentence_is_typed_at_its_pause(self, qapp, mock_settings):
        worker, s = self._partial(qapp, mock_settings, "cuda", hands_free=True)
        assert s["text"] == ["Kısa cümle."]
        assert len(worker._model.transcribe.call_args.args[0]) == int(3.25 * SR)  # middle of the pause

    def test_on_the_cpu_a_short_sentence_still_waits(self, qapp, mock_settings):
        worker, s = self._partial(qapp, mock_settings, "cpu", hands_free=True)
        worker._model.transcribe.assert_not_called()
        assert s["text"] == []

    def test_a_held_key_is_not_cut_early_on_the_gpu(self, qapp, mock_settings):
        """Nothing is typed while a key is held, so a short piece would only split a sentence."""
        worker, s = self._partial(qapp, mock_settings, "cuda", hands_free=False)
        worker._model.transcribe.assert_not_called()

    def test_a_word_or_two_is_not_cut_off_on_its_own(self, qapp, mock_settings):
        """Whisper is unreliable on a second of audio; it goes out with what follows or at the end."""
        worker, s = self._partial(qapp, mock_settings, "cuda", hands_free=True, speech_until=1.0)
        worker._model.transcribe.assert_not_called()


class TestSpeechWithoutAPause:
    """Someone who talks on without pausing gives the pause rule nothing to cut at: a 39.7 s
    dictation showed nothing until it ended (the owner's own voice, 2026-10-10). Hands-free on
    the GPU the model then says where a sentence ends: it splits what it hears into segments,
    and a segment followed by another one is finished. It is typed once two passes in a row
    give it the same words, which keeps the model's first guesses off the page."""

    FIRST = (" Bugün değişiklikleri gözden geçirdim.", 3.2)   # text, where it ends (s)

    def _worker(self, qapp, mock_settings, device="cuda", hands_free=True):
        worker = _make_worker_with_model(qapp, mock_settings)
        worker._device, worker.hands_free = device, hands_free
        return worker, _capture(worker)

    def _snapshot(self, worker, seconds: float, *segments):
        """The recording so far arrives; all of it is speech, with no pause to cut at."""
        worker._model.transcribe.return_value = ([MagicMock(text=t, end=e) for t, e in segments], MagicMock())
        with patch(_CHUNKS, side_effect=lambda rest, *_: [{"start": 0, "end": len(rest)}]):
            worker._transcribe_partial(np.zeros(int(seconds * SR), dtype=np.float32))

    def test_a_finished_sentence_seen_once_is_not_typed_yet(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings)
        self._snapshot(worker, 5, self.FIRST, (" İndirme", 5.0))
        assert s["text"] == []

    def test_it_is_typed_when_the_next_pass_agrees(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings)
        self._snapshot(worker, 5, self.FIRST, (" İndirme", 5.0))
        self._snapshot(worker, 6, self.FIRST, (" İndirme göstergesi", 6.0))
        assert s["text"] == ["Bugün değişiklikleri gözden geçirdim."]

    def test_what_was_typed_is_not_heard_again(self, qapp, mock_settings):
        worker, _ = self._worker(qapp, mock_settings)
        self._snapshot(worker, 5, self.FIRST, (" İndirme", 5.0))
        self._snapshot(worker, 6, self.FIRST, (" İndirme göstergesi", 6.0))
        self._snapshot(worker, 7, (" İndirme göstergesi düzgün", 3.8))
        assert len(worker._model.transcribe.call_args.args[0]) == 7 * SR - int(3.2 * SR)
        assert worker._model.transcribe.call_args.kwargs["initial_prompt"].endswith("gözden geçirdim.")

    def test_a_guess_that_changes_is_never_typed(self, qapp, mock_settings):
        """Measured: "The download indicator will be displayed." became "...works properly and"."""
        worker, s = self._worker(qapp, mock_settings)
        self._snapshot(worker, 4, (" Gösterge görüntülenecek.", 3.0), (" Ve", 4.0))
        self._snapshot(worker, 5, (" Gösterge düzgün çalışıyor.", 4.2), (" Model", 5.0))
        assert s["text"] == []
        self._snapshot(worker, 6, (" Gösterge düzgün çalışıyor.", 4.2), (" Model listesi", 6.0))
        assert s["text"] == ["Gösterge düzgün çalışıyor."]

    def test_a_sentence_still_being_spoken_is_not_typed(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings)
        for seconds in (5, 6, 7):
            self._snapshot(worker, seconds, (" Bugün değişiklikleri gözden", float(seconds)))
        assert s["text"] == []

    def test_a_few_seconds_must_be_waiting_before_the_model_is_asked(self, qapp, mock_settings):
        worker, _ = self._worker(qapp, mock_settings)
        self._snapshot(worker, 2, self.FIRST, (" İndirme", 2.0))
        worker._model.transcribe.assert_not_called()

    def test_an_end_outside_the_audio_is_not_cut_at(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings)
        for seconds in (5, 6):
            self._snapshot(worker, seconds, (" Bugün değişiklikleri gözden geçirdim.", 0.0), (" İndirme", 5.0))
        assert s["text"] == [] and worker._done == 0

    def test_on_the_cpu_the_model_is_not_asked(self, qapp, mock_settings):
        """Every pass would cost seconds there."""
        worker, _ = self._worker(qapp, mock_settings, device="cpu")
        self._snapshot(worker, 6, self.FIRST, (" İndirme", 6.0))
        worker._model.transcribe.assert_not_called()

    def test_under_a_held_key_the_model_is_not_asked(self, qapp, mock_settings):
        worker, _ = self._worker(qapp, mock_settings, hands_free=False)
        self._snapshot(worker, 6, self.FIRST, (" İndirme", 6.0))
        worker._model.transcribe.assert_not_called()

    def test_a_new_dictation_forgets_the_last_one_s_guess(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings)
        self._snapshot(worker, 5, self.FIRST, (" İndirme", 5.0))
        worker._reset_dictation()
        self._snapshot(worker, 5, self.FIRST, (" İndirme", 5.0))
        assert s["text"] == []


class TestPieces:
    """12 s snapshot: 10 s of speech, then 2 s of pause → the cut is in its middle, at 11 s."""
    CUT = 11 * SR
    SNAPSHOT = np.zeros(12 * SR, dtype=np.float32)
    FINISHED = np.zeros(20 * SR, dtype=np.float32)

    def _worker(self, qapp, mock_settings, hands_free: bool):
        worker = _make_worker_with_model(qapp, mock_settings, [" Birinci cümle."])
        worker.hands_free = hands_free
        s = _capture(worker)
        s["ended"] = []
        worker.speech_ended.connect(lambda: s["ended"].append(True))
        return worker, s

    def _piece(self, worker):
        with patch(_CHUNKS, return_value=[_speech(0, 10)]):
            worker._transcribe_partial(self.SNAPSHOT)

    def _finish(self, worker, text=" İkinci cümle."):
        worker._model.transcribe.return_value = ([MagicMock(text=text)] if text else [], MagicMock())
        worker._transcribe(self.FINISHED)

    def test_only_the_speech_before_the_pause_is_transcribed(self, qapp, mock_settings):
        worker, _ = self._worker(qapp, mock_settings, hands_free=False)
        self._piece(worker)
        assert len(worker._model.transcribe.call_args.args[0]) == self.CUT

    def test_no_pause_yet_means_nothing_is_transcribed(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings, hands_free=True)
        with patch(_CHUNKS, return_value=[_speech(0, 12)]):
            worker._transcribe_partial(self.SNAPSHOT)
        worker._model.transcribe.assert_not_called()
        assert s["text"] == [] and s["ended"] == []

    def test_a_held_key_gets_the_whole_text_at_the_release(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings, hands_free=False)
        self._piece(worker)
        assert s["text"] == []  # a paste next to a held key could be a shortcut
        self._finish(worker)
        assert s["text"] == ["Birinci cümle. İkinci cümle."]

    def test_at_the_end_only_the_rest_is_transcribed(self, qapp, mock_settings):
        worker, _ = self._worker(qapp, mock_settings, hands_free=False)
        self._piece(worker)
        self._finish(worker)
        audio = worker._model.transcribe.call_args.args[0]
        assert len(audio) == len(self.FINISHED) - self.CUT
        assert worker._model.transcribe.call_args.kwargs["initial_prompt"].endswith("Birinci cümle.")

    def test_hands_free_types_each_piece_as_it_is_ready(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings, hands_free=True)
        self._piece(worker)
        assert s["text"] == ["Birinci cümle."]
        self._finish(worker)
        assert s["text"] == ["Birinci cümle.", "İkinci cümle."]

    def test_silence_after_typed_pieces_is_not_an_error(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings, hands_free=True)
        self._piece(worker)
        self._finish(worker, text="")
        assert s["text"] == ["Birinci cümle."] and s["errors"] == []

    def test_the_next_dictation_starts_from_scratch(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings, hands_free=False)
        self._piece(worker)
        self._finish(worker)
        self._finish(worker, text=" Yeni dikte.")
        assert s["text"][-1] == "Yeni dikte."
        assert len(worker._model.transcribe.call_args.args[0]) == len(self.FINISHED)

    def test_a_recording_that_was_dropped_leaves_nothing_behind(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings, hands_free=False)
        self._piece(worker)          # then the microphone is lost: no finished recording
        worker.begin_dictation()     # the next recording starts
        worker._queue.put(None)
        with patch.object(worker, "_load_model"):
            worker.run()
        self._finish(worker, text=" Yeni dikte.")
        assert s["text"] == ["Yeni dikte."]

    def test_a_failed_piece_is_left_to_the_final_pass(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings, hands_free=True)
        worker._model.transcribe.side_effect = RuntimeError("boom")
        self._piece(worker)
        assert s["text"] == [] and s["errors"] == []
        worker._model.transcribe.side_effect = None
        self._finish(worker, text=" Hepsi.")
        assert s["text"] == ["Hepsi."]
        assert len(worker._model.transcribe.call_args.args[0]) == len(self.FINISHED)

    def test_hands_free_says_when_the_speaker_has_stopped(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings, hands_free=True)
        with patch(_CHUNKS, return_value=[_speech(0, 4)]):  # 4 s of speech, then 8 s of silence
            worker._transcribe_partial(self.SNAPSHOT)
        assert s["ended"] == [True]

    def test_a_held_key_is_never_ended_by_silence(self, qapp, mock_settings):
        worker, s = self._worker(qapp, mock_settings, hands_free=False)
        with patch(_CHUNKS, return_value=[_speech(0, 4)]):
            worker._transcribe_partial(self.SNAPSHOT)
        assert s["ended"] == []

    def test_a_snapshot_is_only_queued_when_the_worker_is_idle(self, qapp, mock_settings):
        worker, _ = self._worker(qapp, mock_settings, hands_free=False)
        worker.is_ready = True
        worker.add_partial(self.SNAPSHOT)
        worker.add_partial(self.SNAPSHOT)
        assert worker._queue.qsize() == 1


# _load_model: recovery after a failed load (plan 0001)

class TestLoadModelRecovery:

    def test_good_model_loads_again_after_a_failed_load(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"):
            with patch(_PATCH_MODEL_CLS):
                worker._load_model()                                   # 1) model A loads
            with patch(_PATCH_MODEL_CLS, side_effect=Exception("corrupt model")):
                worker._load_model()                                   # 2) broken folder fails
            assert worker.is_ready is False
            with patch(_PATCH_MODEL_CLS):
                worker._load_model()                                   # 3) back to model A
        assert worker.is_ready is True
        assert s["status"][-1] == (STATE_READY, "OK")


# _load_model: success

class TestLoadModelSuccess:

    def _run(self, qapp, mock_settings) -> tuple[TranscriptionWorker, dict]:
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
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
        worker = TranscriptionWorker(mock_settings, MagicMock())
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            worker._load_model()
        _, kwargs = mock_cls.call_args
        assert kwargs.get("local_files_only") is True

    def test_device_is_cpu(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            worker._load_model()
        _, kwargs = mock_cls.call_args
        assert kwargs.get("device") == "cpu"

    def test_compute_type_matches_constant(self, qapp, mock_settings):
        mock_settings.set("compute_type", "int8")
        worker = TranscriptionWorker(mock_settings, MagicMock())
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
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
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._model = MagicMock()
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS), \
             patch("gc.collect") as mock_gc:
            worker._load_model()
        mock_gc.assert_called_once()
        assert worker._model is not None


# _load_model: failure

class TestLoadModelFailure:

    def _run(self, qapp, mock_settings, exc=Exception("model corrupted")) -> tuple[TranscriptionWorker, dict]:
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
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
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/different/folder"), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            worker._load_model()
        wrn_msgs = [m for lvl, _, m in s["logs"] if lvl == "WRN"]
        assert any("invalid" in m for m in wrn_msgs)

    def test_no_wrn_log_when_dir_unchanged(self, qapp, mock_settings):
        mock_settings.set("model_dir", "/correct/folder")
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/correct/folder"), \
             patch(_PATCH_MODEL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            worker._load_model()
        wrn_msgs = [m for lvl, _, m in s["logs"] if lvl == "WRN"]
        assert not any("invalid" in m for m in wrn_msgs)


# _transcribe: model None

class TestTranscribeModelNone:

    def test_emits_err_log(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())  # _model = None
        logs = []
        on_log_entry(lambda l, c, m: logs.append(l))
        worker._transcribe(AUDIO)
        assert "ERR" in logs

    def test_no_text_ready(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
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

    def test_segments_are_joined_with_one_space(self, qapp, mock_settings):
        """Each of Whisper's segments begins with a space of its own."""
        _, s = self._run(qapp, mock_settings, segments_text=[" İlk cümle.", " İkinci cümle."])
        assert s["text"] == ["İlk cümle. İkinci cümle."]

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
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._queue.put(None)
        with patch.object(worker, "_load_model") as mock_load:
            worker.run()
        mock_load.assert_called_once()

    def test_run_poison_pill_exits_loop(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._queue.put(None)
        with patch.object(worker, "_load_model"):
            worker.run()  # must return, not block

    def test_run_dispatches_audio_to_transcribe(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        audio = np.zeros(16000, dtype="float32")
        worker._queue.put(audio)
        worker._queue.put(None)
        with patch.object(worker, "_load_model"), \
             patch.object(worker, "_transcribe") as mock_transcribe:
            worker.run()
        mock_transcribe.assert_called_once_with(audio)

    def test_run_reload_calls_load_model_again(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._queue.put(_RELOAD)
        worker._queue.put(None)
        with patch.object(worker, "_load_model") as mock_load:
            worker.run()
        assert mock_load.call_count == 2  # start + _RELOAD

    def test_run_multiple_audio_chunks(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
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
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._queue.put(np.zeros(8000, dtype="float32"))
        worker._queue.put(None)
        s = _capture(worker)
        with patch.object(worker, "_load_model"), \
             patch.object(worker, "_transcribe", side_effect=MemoryError("RAM full")):
            worker.run()
        assert len(s["errors"]) >= 1

    def test_run_unexpected_exception_emits_err_log(self, qapp, mock_settings):
        """If _transcribe raises an unexpected exception, an ERR log should be written."""
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._queue.put(np.zeros(8000, dtype="float32"))
        worker._queue.put(None)
        s = _capture(worker)
        with patch.object(worker, "_load_model"), \
             patch.object(worker, "_transcribe", side_effect=MemoryError("RAM full")):
            worker.run()
        assert any(lvl == "ERR" for lvl, _, _ in s["logs"])


# _load_model / _transcribe: GPU when usable, CPU otherwise (plan 0009, ADR-0010)

def _gpu(reason=None, compute="float16"):
    """The machine's GPU as core.gpu reports it: usable when reason is None."""
    return patch.multiple("core.gpu",
                          unavailable_reason=MagicMock(return_value=reason),
                          compute_type=MagicMock(return_value=compute))


def _model(text=" Hello world", fails=None):
    model = MagicMock()
    if fails is not None:
        model.transcribe.side_effect = fails
    else:
        model.transcribe.return_value = ([MagicMock(text=text)], MagicMock())
    return model


class TestDeviceSelection:

    def _load(self, worker, model_cls):
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS, side_effect=model_cls) as mock_cls:
            worker._load_model()
        return [(c.kwargs["device"], c.kwargs["compute_type"]) for c in mock_cls.call_args_list]

    def test_auto_uses_the_gpu_when_it_is_usable(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        with _gpu():
            opened = self._load(worker, lambda *a, **k: _model())
        # The precision setting ("int8" here) is a CPU setting; the GPU picks its own.
        assert opened == [("cuda", "float16")]
        assert worker.is_ready is True

    def test_auto_explains_why_the_gpu_is_not_used(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with _gpu(reason="no NVIDIA GPU detected"):
            opened = self._load(worker, lambda *a, **k: _model())
        assert opened == [("cpu", "int8")]
        assert ("...", "STT", "GPU not used: no NVIDIA GPU detected") in s["logs"]

    def test_cpu_setting_never_asks_about_the_gpu(self, qapp, mock_settings):
        mock_settings.set("compute_device", "cpu")
        worker = TranscriptionWorker(mock_settings, MagicMock())
        with _gpu():
            from core import gpu
            opened = self._load(worker, lambda *a, **k: _model())
            gpu.unavailable_reason.assert_not_called()
        assert opened == [("cpu", "int8")]

    def test_a_requested_gpu_that_is_unusable_is_a_warning(self, qapp, mock_settings):
        mock_settings.set("compute_device", "cuda")
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with _gpu(reason="CUDA libraries not found"):
            opened = self._load(worker, lambda *a, **k: _model())
        assert opened == [("cpu", "int8")]
        assert worker.is_ready is True
        assert any(lvl == "WRN" and "CUDA libraries not found" in m for lvl, _, m in s["logs"])

    def test_a_gpu_that_fails_to_load_the_model_falls_back_to_cpu(self, qapp, mock_settings):
        def model_cls(*args, **kwargs):
            if kwargs["device"] == "cuda":
                raise RuntimeError("CUDA out of memory")
            return _model()

        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with _gpu():
            opened = self._load(worker, model_cls)
        assert opened == [("cuda", "float16"), ("cpu", "int8")]
        assert worker.is_ready is True
        assert s["errors"] == []
        assert any(lvl == "WRN" and "CUDA out of memory" in m for lvl, _, m in s["logs"])

    def test_a_gpu_that_fails_the_warm_up_is_replaced_by_the_cpu(self, qapp, mock_settings):
        """The libraries load lazily: a GPU can accept the model and still be unable to run it."""
        def model_cls(*args, **kwargs):
            if kwargs["device"] == "cuda":
                return _model(fails=RuntimeError("Library cublas64_12.dll is not found"))
            return _model()

        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        with _gpu():
            opened = self._load(worker, model_cls)
        assert opened == [("cuda", "float16"), ("cpu", "int8")]
        assert worker.is_ready is True
        assert s["errors"] == []
        assert s["status"][-1] == (STATE_READY, "OK")

    def test_a_cpu_that_fails_the_warm_up_is_not_reloaded(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        with _gpu(reason="no NVIDIA GPU detected"):
            opened = self._load(worker, lambda *a, **k: _model(fails=RuntimeError("boom")))
        assert opened == [("cpu", "int8")]

    def test_a_later_reload_tries_the_gpu_again(self, qapp, mock_settings):
        """Falling back is for this load only; the GPU may be free again next time."""
        attempts = iter([RuntimeError("CUDA out of memory")])

        def model_cls(*args, **kwargs):
            if kwargs["device"] == "cuda":
                error = next(attempts, None)
                if error:
                    raise error
            return _model()

        worker = TranscriptionWorker(mock_settings, MagicMock())
        with _gpu():
            self._load(worker, model_cls)
            assert self._load(worker, model_cls) == [("cuda", "float16")]


class TestModelLoadedReport:
    """model_loaded tells the settings window where the model runs and why not on the GPU."""

    def _reports(self, mock_settings, model_cls, reason=None):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        reports = []
        worker.model_loaded.connect(lambda *args: reports.append(args))
        with _gpu(reason=reason), \
             patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS, side_effect=model_cls):
            worker._load_model()
        return reports

    def test_on_the_gpu(self, qapp, mock_settings):
        assert self._reports(mock_settings, lambda *a, **k: _model()) == [("cuda", "float16", "")]

    def test_on_the_cpu_because_the_gpu_is_unusable(self, qapp, mock_settings):
        reports = self._reports(mock_settings, lambda *a, **k: _model(), reason="no NVIDIA GPU detected")
        assert reports == [("cpu", "int8", "no NVIDIA GPU detected")]

    def test_on_the_cpu_because_the_user_chose_it(self, qapp, mock_settings):
        mock_settings.set("compute_device", "cpu")
        assert self._reports(mock_settings, lambda *a, **k: _model()) == [("cpu", "int8", "compute_device is set to cpu")]

    def test_on_the_cpu_because_the_gpu_load_failed(self, qapp, mock_settings):
        def model_cls(*args, **kwargs):
            if kwargs["device"] == "cuda":
                raise RuntimeError("CUDA out of memory")
            return _model()
        assert self._reports(mock_settings, model_cls) == [("cpu", "int8", "GPU load failed: CUDA out of memory")]

    def test_on_the_cpu_because_the_gpu_failed_the_warm_up(self, qapp, mock_settings):
        def model_cls(*args, **kwargs):
            return _model(fails=RuntimeError("no cublas")) if kwargs["device"] == "cuda" else _model()
        assert self._reports(mock_settings, model_cls) == [
            ("cuda", "float16", ""), ("cpu", "int8", "GPU could not run the model")]

    def test_a_later_gpu_load_clears_the_note(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        reports = []
        worker.model_loaded.connect(lambda *args: reports.append(args))
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS, side_effect=lambda *a, **k: _model()):
            with _gpu(reason="CUDA libraries not found"):
                worker._load_model()
            with _gpu():
                worker._load_model()
        assert reports[-1] == ("cuda", "float16", "")


class TestDictationTimed:
    """dictation_timed: seconds of audio and seconds the model took, for the settings window."""

    def _timings(self, qapp, mock_settings, model):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._model = model
        timings = []
        worker.dictation_timed.connect(lambda *args: timings.append(args))
        worker._transcribe(np.zeros(16000 * 2, dtype=np.float32))
        return timings

    def test_reported_for_a_transcribed_dictation(self, qapp, mock_settings):
        [(audio_seconds, elapsed)] = self._timings(qapp, mock_settings, _model(" Hello world"))
        assert audio_seconds == 2.0
        assert 0 <= elapsed < 1

    def test_not_reported_when_the_transcription_fails(self, qapp, mock_settings):
        assert self._timings(qapp, mock_settings, _model(fails=RuntimeError("boom"))) == []


class TestGpuFailureDuringDictation:
    """GPU memory can run out mid-session (a game starts); the dictation must still be written."""

    def _dictate(self, qapp, mock_settings, cpu_model):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._model = _model(fails=RuntimeError("CUDA out of memory"))
        worker._device = "cuda"
        s = _capture(worker)
        with _gpu(), \
             patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS, return_value=cpu_model) as mock_cls:
            worker._transcribe(AUDIO)
        return s, [c.kwargs["device"] for c in mock_cls.call_args_list]

    def test_the_dictation_is_retried_on_the_cpu(self, qapp, mock_settings):
        s, opened = self._dictate(qapp, mock_settings, _model(" Hello world"))
        assert opened == ["cpu"]
        assert s["text"] == ["Hello world"]
        assert s["errors"] == []
        assert any(lvl == "WRN" and "CUDA out of memory" in m for lvl, _, m in s["logs"])

    def test_it_is_an_error_only_if_the_cpu_fails_too(self, qapp, mock_settings):
        s, _ = self._dictate(qapp, mock_settings, _model(fails=RuntimeError("still broken")))
        assert s["text"] == []
        assert s["errors"] == ["osd.stt_error"]

    def test_a_cpu_failure_is_not_retried(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        worker._model = _model(fails=RuntimeError("boom"))
        with patch(_PATCH_MODEL_CLS) as mock_cls:
            worker._transcribe(AUDIO)
        mock_cls.assert_not_called()
        assert worker._model.transcribe.call_count == 1


class _FakeModel:
    """A model whose destruction can be observed (a MagicMock keeps itself alive in cycles)."""
    def __init__(self):
        self.model = MagicMock()   # the CTranslate2 model inside faster-whisper's wrapper

    def transcribe(self, *args, **kwargs):
        return [], MagicMock()


class TestReplacingAModel:
    """Destroying a CTranslate2 model that has run on the GPU killed Katib (RTX 4080,
    2026-10-09: it died the moment a download finished and it changed models). The GPU model
    gives its memory back and is then kept, never destroyed. These tests hold the rule; the
    crash itself only shows on a real card: scripts/gpu_model_degisimi.py."""

    def _replace(self, worker, old_device: str, **load_kwargs):
        import gc
        import weakref
        old = _FakeModel()
        worker._model, worker._device = old, old_device
        unload, alive = old.model.unload_model, weakref.ref(old)
        del old
        with _gpu(), \
             patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS, side_effect=lambda *a, **k: _FakeModel()):
            worker._load_model(**load_kwargs)
        gc.collect()
        return unload, alive

    def test_a_gpu_model_gives_its_memory_back_and_is_not_destroyed(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        unload, alive = self._replace(worker, "cuda")
        unload.assert_called_once_with()
        assert alive() is not None
        assert worker.is_ready is True

    def test_a_cpu_model_is_destroyed_as_before(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        unload, alive = self._replace(worker, "cpu")
        unload.assert_not_called()
        assert alive() is None

    def test_falling_back_to_the_cpu_does_not_destroy_the_gpu_model_either(self, qapp, mock_settings):
        """The path a GPU failure during a dictation or a warm-up takes."""
        worker = TranscriptionWorker(mock_settings, MagicMock())
        unload, alive = self._replace(worker, "cuda", allow_gpu=False)
        unload.assert_called_once_with()
        assert alive() is not None
        assert worker._device == "cpu"

    def test_every_replaced_gpu_model_is_kept(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        first = self._replace(worker, "cuda")[1]
        second = self._replace(worker, "cuda")[1]
        assert first() is not None and second() is not None

    def test_a_failed_unload_does_not_stop_the_next_model_from_loading(self, qapp, mock_settings):
        import weakref
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        old = _FakeModel()
        old.model.unload_model.side_effect = RuntimeError("CUDA error")
        worker._model, worker._device = old, "cuda"
        alive = weakref.ref(old)
        del old
        with _gpu(), \
             patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS, side_effect=lambda *a, **k: _FakeModel()):
            worker._load_model()
        assert worker.is_ready is True
        assert alive() is not None
        assert any(lvl == "WRN" and "CUDA error" in m for lvl, _, m in s["logs"])


# _load_model: warm-up (plan 0008)

class TestWarmUp:
    """The first transcribe() pays one-off costs; the worker pays them right after loading."""

    def _load(self, worker, transcribe=None, side_effect=None):
        model = MagicMock()
        if transcribe is not None:
            model.transcribe.side_effect = transcribe
        with patch.object(worker.model_provider, "get_active_model_path", return_value="/fake/dir"), \
             patch(_PATCH_MODEL_CLS, return_value=model, side_effect=side_effect):
            worker._load_model()
        return model

    def test_runs_the_decoder_and_the_vad_once_after_loading(self, qapp, mock_settings):
        from workers.transcription_worker import TRANSCRIBE_OPTIONS
        consumed = []

        def transcribe(audio, **kwargs):
            def segments():
                consumed.append(kwargs["vad_filter"])  # faster-whisper decodes lazily
                yield from ()
            return segments(), MagicMock()

        worker = TranscriptionWorker(mock_settings, MagicMock())
        model = self._load(worker, transcribe)
        calls = model.transcribe.call_args_list
        assert len(calls) == 2
        for call in calls:
            audio = call.args[0]
            assert audio.dtype == np.float32 and not audio.any()
        # VAD drops silence before the decoder runs, so one call skips it; the other loads the VAD.
        assert {c.kwargs["vad_filter"] for c in calls} == {False, True}
        assert calls[1].kwargs == {**TRANSCRIBE_OPTIONS, "language": None}
        assert consumed == [False, True]

    def test_uses_the_selected_language(self, qapp, mock_settings):
        mock_settings.set("language", "tr")
        worker = TranscriptionWorker(mock_settings, MagicMock())
        model = self._load(worker, lambda audio, **kw: ([], MagicMock()))
        assert {c.kwargs["language"] for c in model.transcribe.call_args_list} == {"tr"}

    def test_model_is_ready_before_warm_up(self, qapp, mock_settings):
        """Startup is not delayed: a dictation arriving meanwhile is queued, not rejected."""
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        seen = []

        def transcribe(audio, **kwargs):
            seen.append((worker.is_ready, list(s["status"])))
            return [], MagicMock()

        self._load(worker, transcribe)
        assert seen and all(ready and (STATE_READY, "OK") in status for ready, status in seen)

    def test_logs_its_duration(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        self._load(worker, lambda audio, **kw: ([], MagicMock()))
        assert any(c == "STT" and m.startswith("Warm-up done (") for _, c, m in s["logs"])

    def test_failure_is_only_a_warning(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        self._load(worker, RuntimeError("boom"))
        assert worker.is_ready is True
        assert s["errors"] == []
        assert any(lvl == "WRN" and "Warm-up failed: boom" in m for lvl, _, m in s["logs"])

    def test_skipped_when_the_model_failed_to_load(self, qapp, mock_settings):
        worker = TranscriptionWorker(mock_settings, MagicMock())
        s = _capture(worker)
        self._load(worker, side_effect=Exception("corrupt model"))
        assert not any("Warm-up" in m for _, _, m in s["logs"])
