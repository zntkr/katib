import os
import time
import queue
import numpy as np
import subprocess
import requests
import io
import wave
import socket
from typing import TYPE_CHECKING
from pathlib import Path

_CPU_THREADS = 0  # 0: let whisper.cpp analyse hardware automatically.

from PySide6.QtCore import Signal
from workers.base_worker import BaseWorker, measure_time
from core.transcription_filter import TranscriptionFilter
from core.settings import MSG_MODEL_NOT_FOUND, STATE_READY, STATE_PROCESSING


DEVICE        = "cpu"
QUEUE_MAXSIZE = 5

class _ReloadCommand:
    pass

_RELOAD = _ReloadCommand()

def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

class TranscriptionWorker(BaseWorker):
    text_ready            = Signal(str)
    status_changed        = Signal(str, str)  # text, level — "OK"|"ERR"|"WARN"|"IDLE"
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
        self._server_proc = None
        self._port = None
        self.is_ready: bool = False
        self._current_model_dir: str | None = None
        self._filter = TranscriptionFilter()

    def run(self):
        self._load_model()

        while True:
            audio = self._queue.get()

            if audio is None:
                self._stop_server()
                break

            if audio is _RELOAD:
                self._load_model()
                continue

            try:
                self._transcribe(audio)
            except Exception as e:
                detail = str(e) or "unknown error"
                self.log_entry.emit("ERR", "STT", f"Transcription crashed: {detail}")
                self.error_occurred.emit("osd.stt_crashed")
            
    def _stop_server(self):
        if self._server_proc:
            try:
                self._server_proc.terminate()
                self._server_proc.wait(timeout=2)
            except Exception:
                pass
            self._server_proc = None

    def _load_model(self):
        self.is_ready = False
        self._stop_server()

        original_dir = self.settings.get("model_dir")
        valid_path = self.model_provider.get_active_model_path()

        if not valid_path:
            self.status_changed.emit(MSG_MODEL_NOT_FOUND, "WARN")
            self.model_missing.emit()
            return

        if original_dir and valid_path != original_dir:
            self.log_entry.emit("WRN", "STT", f"Selected folder invalid, using: {valid_path}")

        bin_dir = Path(self.model_provider.base_download_dir).parent / "bin"
        server_exe = bin_dir / "whisper-server.exe"

        if not server_exe.exists():
            self.log_entry.emit("ERR", "STT", "whisper-server.exe not found.")
            self.status_changed.emit("status.folder_error", "ERR")
            self.model_missing.emit()
            return

        self.status_changed.emit("status.loading_model", "IDLE")
        self.log_entry.emit("...", "STT", "Starting Whisper Server...")
        self.loading_state_changed.emit(True)

        try:
            self._port = _find_free_port()
            cmd = [
                str(server_exe),
                "-m", valid_path,
                "--port", str(self._port),
                "--host", "127.0.0.1"
            ]

            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            start_time = time.time()
            self._server_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo
            )

            # Wait for server to become available
            server_ready = False
            for _ in range(30):
                try:
                    resp = requests.get(f"http://127.0.0.1:{self._port}/", timeout=1)
                    if resp.status_code == 200:
                        server_ready = True
                        break
                except Exception:
                    pass
                time.sleep(0.5)

            if not server_ready:
                raise RuntimeError("Server failed to respond to HTTP requests.")

            self._current_model_dir = valid_path
            elapsed = time.time() - start_time
            hotkey = self.settings.get("hotkey", "F9").upper()
            self.log_entry.emit("OK", "STT", f"Model ready ({elapsed:.1f}s) — hold {hotkey} to speak")
            self.status_changed.emit(STATE_READY, "OK")
            self.is_ready = True
            self.model_loaded.emit()
            self.loading_state_changed.emit(False)

        except Exception as e:
            detail = str(e) or "unknown error"
            self.log_entry.emit("ERR", "STT", f"Server failed to start: {detail}")
            self.error_occurred.emit("osd.model_load_failed")
            self.status_changed.emit("status.model_error", "ERR")
            self.loading_state_changed.emit(False)

    def stop(self):
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        self._queue.put_nowait(None)

    def reload_model(self):
        try:
            self._queue.put_nowait(_RELOAD)
        except queue.Full:
            self.log_entry.emit("WRN", "STT", "Model reload skipped")

    def check_model_exists(self) -> bool:
        if not self._current_model_dir or not os.path.exists(self._current_model_dir):
            self.error_occurred.emit("osd.model_inaccessible")
            self.log_entry.emit("ERR", "STT", "Model file not found.")
            self.status_changed.emit("status.folder_error", "ERR")
            self.download_state_changed.emit(False)
            return False
        return True

    def add_audio(self, audio) -> None:
        if not self.is_ready:
            return
        try:
            self._queue.put_nowait(audio)
        except queue.Full:
            self.log_entry.emit("WRN", "STT", "Transcription in progress, skipped")
            self.error_occurred.emit("osd.stt_busy")

    @measure_time("STT", "Whisper Transcription")
    def _transcribe(self, audio):
        if not self._server_proc or self._server_proc.poll() is not None:
            self.log_entry.emit("ERR", "STT", "Server is not running.")
            return

        self.log_entry.emit("...", "STT", "Transcription started")
        self.transcription_started.emit()
        self.status_changed.emit(STATE_PROCESSING, "INFO")
        try:
            rms = float(np.sqrt(np.mean(audio ** 2)))
            self.log_entry.emit("...", "STT", f"Audio RMS={rms:.4f}, duration={len(audio)/16000:.1f}s")

            # Convert float32 numpy array to 16-bit PCM WAV in memory
            audio_int16 = (audio * 32767).astype(np.int16)
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_int16.tobytes())
            
            wav_data = wav_io.getvalue()

            lang_setting = self.settings.get("language", "auto")
            target_lang = lang_setting if lang_setting != "auto" else "auto"

            files = {'file': ('audio.wav', wav_data, 'audio/wav')}
            data = {
                'response_format': 'json',
            }
            if target_lang != "auto":
                data['language'] = target_lang

            resp = requests.post(
                f"http://127.0.0.1:{self._port}/inference", 
                files=files, 
                data=data,
                timeout=30
            )
            resp.raise_for_status()

            result = resp.json()
            raw_text = result.get("text", "").strip()

            final_text = self._filter.clean(raw_text)
            
            if not final_text:
                self.log_entry.emit("WRN", "STT", "No speech detected")
                self.error_occurred.emit("osd.no_speech")
                return

            self.log_entry.emit("OK", "STT", f"Transcript: {final_text!r}")
            self.text_ready.emit(final_text)

        except requests.exceptions.RequestException as e:
            self.log_entry.emit("ERR", "STT", f"HTTP Error: {e}")
            self.error_occurred.emit("osd.stt_error")
        except Exception as e:
            self.log_entry.emit("ERR", "STT", f"Transcription error: {e}")
            self.error_occurred.emit("osd.stt_error")
        finally:
            self.transcription_finished.emit()
            if self.is_ready:
                self.status_changed.emit(STATE_READY, "OK")
