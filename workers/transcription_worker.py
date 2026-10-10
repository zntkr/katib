import time
import queue
import numpy as np
from typing import TYPE_CHECKING

_CPU_THREADS = 0  # 0: CTranslate2's default, 4 threads (faster-whisper docs); plan 0012 Faz 3 measures more.

from PySide6.QtCore import Signal

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

from workers.base_worker import BaseWorker, measure_time
from core import gpu
from core.log import get_logger, OK
from core.segmenter import (
    MIN_SEGMENT_SECONDS, MIN_SEGMENT_SECONDS_FAST, context_prompt, next_cut, speech_chunks, speech_is_over,
)
from core.transcription_filter import TranscriptionFilter
from core.settings import MSG_MODEL_NOT_FOUND, STATE_READY, STATE_LOADING


_log = get_logger("STT")

SAMPLE_RATE   = 16000
QUEUE_MAXSIZE = 5

# Decoding options. scripts/olcum.py uses the same dict, so measurements test what users run.
TRANSCRIBE_OPTIONS = {
    "beam_size"                 : 5,
    # faster-whisper's default retries a low-confidence window at up to six temperatures; one
    # hesitant 9 s stretch then stalled a dictation for 57 s. One retry still rescues a loop.
    "temperature"               : [0.0, 0.4],
    "vad_filter"                : True,
    "vad_parameters"            : {
        "threshold"              : 0.4,
        "min_speech_duration_ms" : 200,
        "min_silence_duration_ms": 500,
    },
    "no_speech_threshold"       : 0.6,
    "condition_on_previous_text": False,
}


def warm_up(model, language: str | None, options: dict = TRANSCRIBE_OPTIONS) -> None:
    """Pays the first transcribe()'s one-off costs (CTranslate2 sets up its kernels,
    faster-whisper loads the VAD model). scripts/olcum.py calls it too, so its first
    measured recording is not a cold start. Raises whatever the model raises."""
    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    # VAD drops silence before the decoder runs, so the decoder needs a call without it.
    for run_options in (dict(options, vad_filter=False), options):
        segments, _ = model.transcribe(silence, language=language, **run_options)
        for _ in segments:  # decoding is lazy
            pass


class _ReloadCommand:
    pass

_RELOAD = _ReloadCommand()
_NEW_DICTATION = object()  # queue marker: a recording started, forget the previous one's pieces


class _Partial:
    """The recording so far, sent while the user is still speaking (plan 0014)."""
    def __init__(self, audio):
        self.audio = audio

class TranscriptionWorker(BaseWorker):
    text_ready            = Signal(str)
    status_changed        = Signal(str, str)  # model status key, level — no model / loading / ready / error
    loading_state_changed = Signal(bool)
    model_missing         = Signal()  # no valid model directory → show download button
    # Model loaded: device ("cuda" | "cpu"), compute type, and why the GPU is not used ("" if it is).
    model_loaded          = Signal(str, str, str)
    transcription_started = Signal()
    transcription_finished = Signal()
    dictation_timed       = Signal(float, float)  # seconds of audio, seconds the model took
    speech_ended          = Signal()  # hands-free dictation: the speaker has stopped

    def __init__(self, settings, model_provider, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.model_provider = model_provider
        self._queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._model: "WhisperModel | None" = None
        self.is_ready: bool = False
        self.is_loading: bool = True  # run() loads the model first; False once an attempt ends
        self._current_model_dir: str | None = None
        self._device = "cpu"  # where the loaded model runs: "cuda" or "cpu"
        self._retired_gpu_models: list = []  # replaced GPU models, never destroyed (_release_model)
        self._gpu_note = ""   # why the GPU is not used; shown next to the device in the settings window
        self._filter = TranscriptionFilter()
        # Set by TrayApp: nobody holds the key, so pieces are typed as soon as they are ready
        # and the worker says when the speaker has stopped. While a key is held pieces wait
        # for the release: a paste (Ctrl+V) next to a held F4 would be Ctrl+F4.
        self.hands_free = False
        # The dictation in flight (worker thread only): samples already transcribed, their
        # texts, and how many of those texts were already typed.
        self._done = 0
        self._pieces: list[str] = []
        self._typed = 0

    # ------------------------------------------------------------------ QThread
    def run(self):
        self._load_model()

        while True:
            audio = self._queue.get()   # blocking wait — no CPU usage

            if audio is None:           # poison pill: shut down the thread
                break

            if audio is _RELOAD:
                self._load_model()
                continue

            if audio is _NEW_DICTATION:
                self._reset_dictation()
                continue

            if isinstance(audio, _Partial):
                self._transcribe_partial(audio.audio)
                continue

            try:
                self._transcribe(audio)
            except Exception as e:
                detail = str(e) or "unknown error"
                _log.error(f"Transcription crashed: {detail}")
                self.error_occurred.emit("osd.stt_crashed")
            
    def _load_model(self, allow_gpu: bool = True):
        self.is_ready = False
        self.is_loading = True
        try:
            self._load_model_inner(allow_gpu)
        finally:
            self.is_loading = False
        if self.is_ready and not self._warm_up() and self._device == "cuda":
            # The CUDA libraries load lazily: a GPU can accept the model and still fail to run it.
            _log.warning("GPU could not run the model, switching to CPU")
            self._gpu_note = "GPU could not run the model"
            self._load_model(allow_gpu=False)

    def _warm_up(self) -> bool:
        """Pay the first transcribe()'s one-off costs now, not on the first dictation.
        The model is already ready: a dictation arriving meanwhile waits in the queue."""
        start = time.perf_counter()
        try:
            warm_up(self._model, self._target_language())
        except Exception as e:
            _log.warning(f"Warm-up failed: {e}")
            return False
        _log.info(f"Warm-up done ({(time.perf_counter() - start) * 1000:.0f} ms)")
        return True

    def _gpu_compute_type(self, allow_gpu: bool) -> str | None:
        """The compute type for a GPU load, or None when the model must go to the CPU (ADR-0010)."""
        if not allow_gpu:
            return None  # falling back after a GPU failure; the caller has set _gpu_note
        preference = self.settings.get("compute_device")
        if preference == "cpu":
            self._gpu_note = "compute_device is set to cpu"
            return None
        reason = gpu.unavailable_reason()
        self._gpu_note = reason or ""
        if reason is None:
            return gpu.compute_type()
        if preference == "cuda":
            _log.warning(f"GPU requested but not usable: {reason}")
        else:
            _log.info(f"GPU not used: {reason}")
        return None

    def _open_model(self, model_cls, model_dir: str, allow_gpu: bool):
        """Loads on the GPU when it is usable; any GPU failure ends on the CPU, as before GPU support."""
        def open_on(device: str, compute_type: str):
            _log.info(f"Loading ({device}/{compute_type})")
            return model_cls(
                model_dir,
                device           = device,
                compute_type     = compute_type,
                local_files_only = True,
                cpu_threads      = _CPU_THREADS,
            )

        gpu_compute_type = self._gpu_compute_type(allow_gpu)
        if gpu_compute_type is not None:
            try:
                return open_on("cuda", gpu_compute_type), "cuda", gpu_compute_type
            except Exception as e:
                self._gpu_note = f"GPU load failed: {str(e) or 'unknown error'}"
                _log.warning(f"GPU load failed ({str(e) or 'unknown error'}), using CPU")
        cpu_compute_type = self.settings.get("compute_type")
        return open_on("cpu", cpu_compute_type), "cpu", cpu_compute_type

    def _release_model(self) -> None:
        """Lets go of the loaded model before another one is loaded."""
        model = self._model
        self._model = None  # not `del`: the attribute must survive a failed load (plan 0001)
        if model is None:
            return
        if self._device == "cuda":
            # Destroying a model that has run on the GPU can kill the process: an unhandled C++
            # exception inside CTranslate2 4.7.1 on Windows (0xe06d7363, then abort). Seen on an
            # RTX 4080, 2026-10-09: Katib died the moment a download finished and it changed
            # models. Reproduced with the speech language set to "tr", not with automatic
            # detection. unload_model() gives the GPU memory back without destroying anything
            # (measured: about 50 MB stays per replaced model), so the object is kept until
            # Katib exits; main.py leaves through os._exit, which runs no destructors.
            # Check on a real card: scripts/gpu_model_degisimi.py.
            try:
                model.model.unload_model()
            except Exception as e:
                _log.warning(f"The previous model's GPU memory was not released: {e}")
            self._retired_gpu_models.append(model)
            return
        del model
        import gc
        gc.collect()

    def _load_model_inner(self, allow_gpu: bool = True):
        original_dir = self.settings.get("model_dir")
        valid_dir = self.model_provider.get_active_model_path()

        if not valid_dir:
            self.status_changed.emit(MSG_MODEL_NOT_FOUND, "WARN")
            self.model_missing.emit()
            return

        if original_dir and valid_dir != original_dir:
            _log.warning(f"Selected folder invalid, using: {valid_dir}")

        self.status_changed.emit(STATE_LOADING, "IDLE")
        self.loading_state_changed.emit(True)

        try:
            self._release_model()

            from faster_whisper import WhisperModel
            start_time = time.time()
            self._model, self._device, compute_type = self._open_model(WhisperModel, valid_dir, allow_gpu)
            self._current_model_dir = valid_dir
            elapsed = time.time() - start_time
            hotkey = self.settings.get("hotkey", "F9").upper()
            _log.log(OK, f"Model ready ({elapsed:.1f}s) — hold {hotkey} to speak")
            self.status_changed.emit(STATE_READY, "OK")
            self.is_ready = True
            self.model_loaded.emit(self._device, compute_type, self._gpu_note)
            self.loading_state_changed.emit(False)
        except Exception as e:
            detail = str(e) or "unknown error"
            _log.error(f"Model failed to load: {detail}")
            self.error_occurred.emit("osd.model_load_failed")
            self.status_changed.emit("status.model_error", "ERR")
            self.loading_state_changed.emit(False)

    def stop(self):
        # put() would block forever on a full queue; drain it first.
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        self._queue.put_nowait(None)    # exit signal for the run loop

    # ---------------------------------------------------------- public control
    def reload_model(self):
        try:
            self._queue.put_nowait(_RELOAD)
        except queue.Full:
            _log.warning("Model reload skipped")

    def add_audio(self, audio) -> None:
        """Enqueues the numpy array from AudioWorker; rejects it if the queue is full."""
        if not self.is_ready:
            # The model was reloaded or lost between key press and release. Report it,
            # otherwise the OSD would stay on "Listening" forever.
            _log.warning("Model not ready, recording discarded")
            self.error_occurred.emit(STATE_LOADING if self.is_loading else MSG_MODEL_NOT_FOUND)
            return
        try:
            self._queue.put_nowait(audio)
        except queue.Full:
            _log.warning("Transcription in progress, skipped")
            self.error_occurred.emit("osd.stt_busy")

    def begin_dictation(self) -> None:
        """AudioWorker.recording_started. A recording that never reaches add_audio (too
        short, microphone lost) must not leave its pieces to the next one."""
        try:
            self._queue.put_nowait(_NEW_DICTATION)
        except queue.Full:
            pass  # finished dictations are waiting; each of them resets the state too

    def add_partial(self, audio) -> None:
        """AudioWorker.partial_audio. Only looked at when the worker is idle: the finished
        recording covers everything, so a skipped snapshot loses nothing."""
        if self.is_ready and self._queue.empty():
            try:
                self._queue.put_nowait(_Partial(audio))
            except queue.Full:
                pass

    # ----------------------------------------------------------------- private
    def _target_language(self) -> str | None:
        lang = self.settings.get("language", "auto")
        return None if lang == "auto" else lang

    def _decode(self, audio) -> str:
        if len(audio) == 0:
            return ""
        segments, _ = self._model.transcribe(
            audio,
            language       = self._target_language(),
            # Earlier pieces of this dictation carry capitals, punctuation and terms over the cut.
            initial_prompt = context_prompt(self.settings.get("initial_prompt", ""), " ".join(self._pieces)),
            **TRANSCRIBE_OPTIONS,
        )
        segments = list(segments)  # decoding happens here
        if any(isinstance(seg.temperature, float) and seg.temperature > 0 for seg in segments):
            _log.info("Low-confidence audio: decoded a second time")
        # Each segment's text begins with a space of its own: joined as they are, two
        # sentences of one decode came out with two spaces between them.
        return " ".join(text for text in (seg.text.strip() for seg in segments) if text)

    def _reset_dictation(self) -> None:
        self._done, self._pieces, self._typed = 0, [], 0

    def _emit_untyped(self) -> str:
        """Hands the pieces not typed yet to the UI as one text."""
        text = " ".join(self._pieces[self._typed:])
        self._typed = len(self._pieces)
        if text:
            _log.log(OK, "Transcript", extra={"transcript": text})
            self.text_ready.emit(text)
        return text

    def _transcribe_partial(self, audio) -> None:
        """While the user is still speaking: transcribes the speech up to a real pause, so
        only the rest is left when the dictation ends. Hands-free, it also types the piece
        and notices that the speaker has stopped. Any failure is left to the final pass."""
        if self._model is None:
            return
        try:
            rest = audio[self._done:]
            speeches = speech_chunks(rest, TRANSCRIBE_OPTIONS["vad_parameters"]["threshold"])
            # Pieces are typed only hands-free; under a held key a short one would just split a sentence.
            fast = self.hands_free and self._device == "cuda"
            cut = next_cut(speeches, len(rest),
                           min_segment_seconds=MIN_SEGMENT_SECONDS_FAST if fast else MIN_SEGMENT_SECONDS)
            if cut is None:
                if self.hands_free and speech_is_over(speeches, len(rest), heard_before=self._done > 0):
                    self.speech_ended.emit()
                return
            started = time.perf_counter()
            text = self._filter.clean(self._decode(rest[:cut]), duration=cut / SAMPLE_RATE)
            self._done += cut
            _log.info(f"Piece transcribed while recording: {cut / SAMPLE_RATE:.1f}s of audio "
                      f"in {(time.perf_counter() - started) * 1000:.0f} ms")
            if text:
                self._pieces.append(text)
                if self.hands_free:
                    self._emit_untyped()
        except Exception as e:
            _log.warning(f"Background transcription skipped: {str(e) or 'unknown error'}")

    @measure_time("STT", "Whisper Transcription")
    def _transcribe(self, audio):
        if self._model is None:
            _log.error("Model not loaded, cannot transcribe.")
            return

        _log.info("Transcription started")
        self.transcription_started.emit()
        try:
            rms = float(np.sqrt(np.mean(audio ** 2)))
            _log.info(f"Audio RMS={rms:.4f}, duration={len(audio)/SAMPLE_RATE:.1f}s")

            rest = audio[self._done:]  # what was not transcribed while the user was speaking
            started = time.perf_counter()
            try:
                raw_text = self._decode(rest)
            except Exception as e:
                if self._device != "cuda":
                    raise
                # GPU memory can run out mid-session (e.g. a game starts); the CPU still works.
                _log.warning(f"GPU transcription failed ({str(e) or 'unknown error'}), switching to CPU")
                self._gpu_note = f"GPU failed during a dictation: {str(e) or 'unknown error'}"
                self._load_model(allow_gpu=False)
                if not self.is_ready:
                    raise
                started = time.perf_counter()
                raw_text = self._decode(rest)
            self.dictation_timed.emit(len(audio) / SAMPLE_RATE, time.perf_counter() - started)

            last_text = self._filter.clean(raw_text, duration=len(rest) / SAMPLE_RATE)
            if last_text:
                self._pieces.append(last_text)

            if not self._pieces:
                _log.warning("No speech detected")
                self.error_occurred.emit("osd.no_speech")
                return

            self._emit_untyped()

        except Exception as e:
            _log.error(f"Transcription error: {e}")
            self.error_occurred.emit("osd.stt_error")
        finally:
            self._reset_dictation()
            self.transcription_finished.emit()
