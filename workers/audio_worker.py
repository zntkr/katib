import threading
import sys
import numpy as np
from PySide6.QtCore import Signal, QElapsedTimer

from workers.base_worker import BaseWorker
from core.audio_source import AudioSource, AudioDeviceError, AudioDisconnectedError

SAMPLE_RATE              = 16000
MIN_RECORDING_DURATION   = 0.5    # seconds — shorter recordings are discarded

def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Linear interpolation resample. Sufficient quality for speech recognition."""
    if orig_sr == target_sr:
        return audio
    new_len = int(len(audio) * target_sr / orig_sr)
    return np.interp(
        np.linspace(0, len(audio) - 1, new_len),
        np.arange(len(audio)),
        audio,
    ).astype(np.float32)

class AudioWorker(BaseWorker):
    audio_ready        = Signal(object)  # numpy array (float32, 16kHz, mono)
    level_changed      = Signal(float)   # 0.0 – 1.0
    devices_ready      = Signal(list)    # list of (label: str, index: int, is_default: bool)
    speech_detected    = Signal(bool)    # dynamic VAD state for UI
    muted_detected     = Signal()        # mathematical 0.0 (muted) detected
    recording_finished = Signal()        # emitted when recording stops (in all cases)
    audio_failed       = Signal()        # recording too short or silent
    mic_unavailable    = Signal()        # hardware unreachable (not found / failed to open / disconnected)

    def __init__(self, settings, audio_source: AudioSource, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.audio_source = audio_source
        
        self._device_index: int | None = None
        self._chunks: list = []
        self._rms_history: list = []
        self._running_noise_floor: float = -120.0
        self._chunks_lock              = threading.Lock()
        
        # Keep track if we are actively recording.
        self._is_recording = False
        
        # Initially unset (False); calling set() unblocks the thread's wait() and stops it.
        self._stop_event = threading.Event()
        self._silence_timer = QElapsedTimer()
        self._silence_notified = False

    # ------------------------------------------------------------------ QThread
    def run(self):
        """Keeps the thread alive; recording is managed externally via start/stop."""
        self._stop_event.wait()   # blocks while False; stop() calls set() to unblock

    def stop(self):
        self._stop_event.set()
        self.audio_source.stop()

    # ---------------------------------------------------------- public control
    def set_device(self, device_index: int) -> None:
        if self._device_index == device_index:
            return
            
        self._device_index = device_index
        try:
            label = self.audio_source.set_device(device_index)
            self.log_entry.emit("OK", "MIC", f"Device → {label}")
        except AudioDeviceError as e:
            self.log_entry.emit("ERR", "MIC", f"Device error: {e}")
            self._device_index = None

    def refresh_devices(self) -> None:
        """Queries available microphones and reports them via the devices_ready signal."""
        items = self.audio_source.refresh_devices()
        self.devices_ready.emit(items)
        if not items:
            self.mic_unavailable.emit()

    def start_recording(self):
        if self._is_recording:
            return  # already recording

        if self._device_index is None:
            self.log_entry.emit("ERR", "MIC", "No microphone selected.")
            self.error_occurred.emit("osd.mic_no_device")
            return

        with self._chunks_lock:
            self._chunks.clear()
            self._rms_history.clear()
            self._running_noise_floor = -120.0

        try:
            self.audio_source.start(self._audio_callback, self._on_stream_finished)
            self._is_recording = True
            self._silence_timer.invalidate()
            self._silence_notified = False
            self.log_entry.emit("OK", "MIC", "Recording started")
        except AudioDeviceError as e:
            msg = str(e)
            if "not connected" in msg.lower():
                self.log_entry.emit("ERR", "MIC", "Microphone not connected")
                self.error_occurred.emit("osd.mic_not_connected")
            else:
                self.log_entry.emit("ERR", "MIC", f"Microphone could not be opened: {e}")
                self.error_occurred.emit("osd.mic_open_failed")
            self.mic_unavailable.emit()
            self._is_recording = False
        except Exception as e:
            self.log_entry.emit("ERR", "MIC", f"Microphone could not be opened: {e}")
            self.error_occurred.emit("osd.mic_open_failed")
            self.mic_unavailable.emit()
            self._is_recording = False

    def stop_recording(self):
        if not self._is_recording:
            self.recording_finished.emit()  # count as finished even if there was no stream
            return

        self.audio_source.stop()
        self._is_recording = False
        
        self.level_changed.emit(0.0)
        self.recording_finished.emit()

        with self._chunks_lock:
            chunks_snapshot = list(self._chunks)
            self._chunks.clear()

        if not chunks_snapshot:
            self.log_entry.emit("WRN", "MIC", "Recording is empty")
            self.audio_failed.emit()
            return

        try:
            audio = np.concatenate(chunks_snapshot, axis=0).flatten()
            native_sr = self.audio_source.native_sample_rate
            if native_sr != SAMPLE_RATE:
                audio = _resample(audio, native_sr, SAMPLE_RATE)
                
            duration = len(audio) / SAMPLE_RATE
            if duration < MIN_RECORDING_DURATION:
                self.log_entry.emit("WRN", "MIC", "Recording too short, skipped")
                self.audio_failed.emit()
                return
                
            from core.transcription_filter import analyse_vad, is_silent
            chunk_duration = len(audio) / SAMPLE_RATE / len(self._rms_history) if self._rms_history else 0.1
            stats = analyse_vad(self._rms_history, chunk_duration)
            
            if is_silent(stats):
                self.log_entry.emit("WRN", "MIC", f"Audio discarded as silence/noise (Noise floor: {stats['noise_db']:.1f} dB, Speech peak: {stats['speech_db']:.1f} dB, Voiced: {stats['voiced_seconds']:.2f}s)")
                self.error_occurred.emit("osd.audio_too_quiet")
                self.audio_failed.emit()
                return
                
            self.log_entry.emit("OK", "MIC", f"Recording complete ({duration:.1f}s)")
            self.audio_ready.emit(audio)
        except Exception as e:
            self.log_entry.emit("ERR", "MIC", f"Audio merge error: {e}")
            self.error_occurred.emit("osd.audio_merge_error")

    # ----------------------------------------------------------------- private

    def _audio_callback(self, indata: np.ndarray, status_msg: str | None):
        try:
            if status_msg:
                self.log_entry.emit("WRN", "MIC", f"Status: {status_msg}")

            if indata is not None:
                rms = float(np.sqrt(np.mean(indata ** 2)))
                if not np.isfinite(rms):
                    return
                
                from core.transcription_filter import to_db
                chunk_db = to_db(rms)
                
                if self._running_noise_floor == -120.0 or chunk_db < self._running_noise_floor:
                    self._running_noise_floor = chunk_db
                else:
                    self._running_noise_floor += 0.02  # slowly creep up to adapt to changing environments
                
                is_speech = chunk_db > self._running_noise_floor + 10.0
                self.speech_detected.emit(is_speech)
                
                with self._chunks_lock:
                    self._chunks.append(indata.copy())
                    self._rms_history.append(rms)

                self.level_changed.emit(min(rms * 5.0, 1.0))

                # Mute detection: mathematical 0.0 sustained for > 1500 ms.
                if rms == 0.0:
                    if not self._silence_timer.isValid():
                        self._silence_timer.start()
                    elif self._silence_timer.elapsed() > 1500 and not self._silence_notified:
                        self._silence_notified = True
                        self.muted_detected.emit()
                        # Short beep on a separate thread so the audio callback is not blocked.
                        def _beep():
                            if sys.platform == "win32":
                                import winsound
                                winsound.Beep(440, 100)
                                winsound.Beep(440, 100)
                            else:
                                import subprocess
                                subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"],
                                               capture_output=True)
                        import threading
                        threading.Thread(target=_beep, daemon=True).start()
                else:
                    self._silence_timer.invalidate()
                    self._silence_notified = False
        except Exception:
            self.log_entry.emit("ERR", "MIC", "Audio stream interrupted")

    def _on_stream_finished(self, err: Exception | None) -> None:
        """Called when the stream closes. If err is not None, it closed unexpectedly."""
        self._is_recording = False
        try:
            if err is None:
                return # Intentional close
                
            self.log_entry.emit("ERR", "MIC", "Connection lost")
            self.error_occurred.emit("osd.mic_disconnected")
            self.mic_unavailable.emit()
            self.level_changed.emit(0.0)
            self.refresh_devices()  # auto-refresh the device list
        except Exception:
            self.log_entry.emit("ERR", "MIC", "Stream close error")