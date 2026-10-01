import time
import queue
import numpy as np
from typing import TYPE_CHECKING

_CPU_THREADS = 0  # 0: let CTranslate2 analyse hardware automatically.

from PySide6.QtCore import Signal

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

from workers.base_worker import BaseWorker, measure_time
from core.log import get_logger, OK
from core.transcription_filter import TranscriptionFilter
from core.settings import MSG_MODEL_NOT_FOUND, STATE_READY, STATE_LOADING


_log = get_logger("STT")

DEVICE        = "cpu"
QUEUE_MAXSIZE = 5

class _ReloadCommand:
    pass

_RELOAD = _ReloadCommand()

class TranscriptionWorker(BaseWorker):
    text_ready            = Signal(str)
    status_changed        = Signal(str, str)  # model status key, level — no model / loading / ready / error
    loading_state_changed = Signal(bool)
    model_missing         = Signal()  # no valid model directory → show download button
    model_loaded          = Signal()  # model loaded successfully → hide download button
    transcription_started = Signal()
    transcription_finished = Signal()

    def __init__(self, settings, model_provider, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.model_provider = model_provider
        self._queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._model: "WhisperModel | None" = None
        self.is_ready: bool = False
        self.is_loading: bool = True  # run() loads the model first; False once an attempt ends
        self._current_model_dir: str | None = None
        self._filter = TranscriptionFilter()

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

            try:
                self._transcribe(audio)
            except Exception as e:
                detail = str(e) or "unknown error"
                _log.error(f"Transcription crashed: {detail}")
                self.error_occurred.emit("osd.stt_crashed")
            
    def _load_model(self):
        self.is_ready = False
        self.is_loading = True
        try:
            self._load_model_inner()
        finally:
            self.is_loading = False

    def _load_model_inner(self):
        original_dir = self.settings.get("model_dir")
        valid_dir = self.model_provider.get_active_model_path()

        if not valid_dir:
            self.status_changed.emit(MSG_MODEL_NOT_FOUND, "WARN")
            self.model_missing.emit()
            return

        if original_dir and valid_dir != original_dir:
            _log.warning(f"Selected folder invalid, using: {valid_dir}")

        device       = "cpu"
        compute_type = self.settings.get("compute_type")

        self.status_changed.emit(STATE_LOADING, "IDLE")
        _log.info(f"Loading ({device}/{compute_type})")
        self.loading_state_changed.emit(True)

        try:
            if self._model is not None:
                del self._model
                import gc
                gc.collect()

            from faster_whisper import WhisperModel
            start_time = time.time()
            self._model = WhisperModel(
                valid_dir,
                device           = device,
                compute_type     = compute_type,
                local_files_only = True,
                cpu_threads      = _CPU_THREADS,
            )
            self._current_model_dir = valid_dir
            elapsed = time.time() - start_time
            hotkey = self.settings.get("hotkey", "F9").upper()
            _log.log(OK, f"Model ready ({elapsed:.1f}s) — hold {hotkey} to speak")
            self.status_changed.emit(STATE_READY, "OK")
            self.is_ready = True
            self.model_loaded.emit()
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

    # ----------------------------------------------------------------- private
    @measure_time("STT", "Whisper Transcription")
    def _transcribe(self, audio):
        if self._model is None:
            _log.error("Model not loaded, cannot transcribe.")
            return

        _log.info("Transcription started")
        self.transcription_started.emit()
        try:
            rms = float(np.sqrt(np.mean(audio ** 2)))
            _log.info(f"Audio RMS={rms:.4f}, duration={len(audio)/16000:.1f}s")

            lang_setting = self.settings.get("language", "auto")
            target_lang = lang_setting if lang_setting != "auto" else None

            prompt = self.settings.get("initial_prompt", "").strip()

            segments, _ = self._model.transcribe(
                audio,
                language                  = target_lang,
                beam_size                 = 5,
                vad_filter                = True,
                vad_parameters            = {
                    "threshold"              : 0.4,
                    "min_speech_duration_ms" : 200,
                    "min_silence_duration_ms": 500,
                },
                no_speech_threshold       = 0.6,
                initial_prompt            = prompt,
                condition_on_previous_text= False,
            )

            raw_text = " ".join(seg.text for seg in segments).strip()

            final_text = self._filter.clean(raw_text)
            
            if final_text is None:
                _log.warning("No speech detected")
                self.error_occurred.emit("osd.no_speech")
                return

            _log.log(OK, "Transcript", extra={"transcript": final_text})
            self.text_ready.emit(final_text)

        except Exception as e:
            _log.error(f"Transcription error: {e}")
            self.error_occurred.emit("osd.stt_error")
        finally:
            self.transcription_finished.emit()
