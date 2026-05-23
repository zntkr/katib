import os
import time
import queue
import numpy as np
from typing import TYPE_CHECKING

_CPU_THREADS = 0  # 0: let CTranslate2 analyse hardware automatically.

from PySide6.QtCore import Signal

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

from workers.base_worker import BaseWorker, measure_time
from core.transcription_filter import TranscriptionFilter
from core.settings import MSG_MODEL_NOT_FOUND, STATE_READY, STATE_PROCESSING


DEVICE        = "cpu"
QUEUE_MAXSIZE = 5

class _ReloadCommand:
    pass

_RELOAD = _ReloadCommand()

class TranscriptionWorker(BaseWorker):
    text_ready            = Signal(str)
    status_changed        = Signal(str, str)  # text, level — "OK"|"ERR"|"WARN"|"IDLE"
    loading_state_changed = Signal(bool)
    model_missing         = Signal()  # no valid model directory → show download button
    model_loaded          = Signal()  # model loaded successfully → hide download button
    transcription_started = Signal()
    transcription_finished = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._model: "WhisperModel | None" = None
        self.is_ready: bool = False
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
                detail = str(e) or "bilinmeyen hata"
                self.log_entry.emit("ERR", "STT", f"Transcription crashed: {detail}")
                self.error_occurred.emit("Transcription crashed")
            
    def _load_model(self):
        self.is_ready = False
        original_dir = self.settings.get("model_dir")
        valid_dir = self.settings.get_resolved_model_dir()

        if not valid_dir:
            self.log_entry.emit("WRN", "STT", "No model found")
            self.status_changed.emit(MSG_MODEL_NOT_FOUND, "WARN")
            self.model_missing.emit()
            return

        if original_dir and valid_dir != original_dir:
            self.log_entry.emit("WRN", "STT", f"Selected folder invalid, using: {valid_dir}")

        device       = "cpu"
        compute_type = self.settings.get("compute_type")

        self.status_changed.emit("status.loading_model", "IDLE")
        self.log_entry.emit("...", "STT", f"Loading ({device}/{compute_type})")
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
            self.log_entry.emit("OK", "STT", f"Model ready ({elapsed:.1f}s) — hold {hotkey} to speak")
            self.status_changed.emit(STATE_READY, "OK")
            self.is_ready = True
            self.model_loaded.emit()
            self.loading_state_changed.emit(False)
        except Exception as e:
            detail = str(e) or "bilinmeyen hata"
            self.log_entry.emit("ERR", "STT", f"Model failed to load: {detail}")
            self.error_occurred.emit("Model failed to load")
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
            self.log_entry.emit("WRN", "STT", "Model reload skipped")

    def check_model_exists(self) -> bool:
        if not self._current_model_dir or not os.path.exists(self._current_model_dir):
            self.error_occurred.emit("Model folder inaccessible")
            self.log_entry.emit("ERR", "STT", "Model folder not found.")
            self.status_changed.emit("status.folder_error", "ERR")
            return False
        return True

    def add_audio(self, audio) -> None:
        """Enqueues the numpy array from AudioWorker; rejects it if the queue is full."""
        if not self.is_ready:
            return
        try:
            self._queue.put_nowait(audio)
        except queue.Full:
            self.log_entry.emit("WRN", "STT", "Transcription in progress, skipped")
            self.error_occurred.emit("Transcription in progress")

    # ----------------------------------------------------------------- private
    @measure_time("STT", "Whisper Transcription")
    def _transcribe(self, audio):
        if self._model is None:
            self.log_entry.emit("ERR", "STT", "Model not loaded, cannot transcribe.")
            return

        self.log_entry.emit("...", "STT", "Transcription started")
        self.transcription_started.emit()
        self.status_changed.emit(STATE_PROCESSING, "INFO")
        try:
            rms = float(np.sqrt(np.mean(audio ** 2)))
            self.log_entry.emit("...", "STT", f"Audio RMS={rms:.4f}, duration={len(audio)/16000:.1f}s")

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
                self.log_entry.emit("WRN", "STT", "No speech detected")
                return

            self.log_entry.emit("OK", "STT", f"Transcript: {final_text!r}")
            self.text_ready.emit(final_text)

        except Exception:
            self.log_entry.emit("ERR", "STT", "Transcription error")
            self.error_occurred.emit("Transcription error")
        finally:
            self.transcription_finished.emit()
            if self.is_ready:
                self.status_changed.emit(STATE_READY, "OK")
