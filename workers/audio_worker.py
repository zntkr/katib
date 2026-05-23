import threading
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd
import winsound
from PySide6.QtCore import Signal, QElapsedTimer

from workers.base_worker import BaseWorker

if TYPE_CHECKING:
    pass  # sd.InputStream is a runtime type, accessed via sd module

# In test environments sd is mocked; sd.PortAudioError may not be a real exception class.
try:
    _PortAudioError: type[Exception] = sd.PortAudioError  # type: ignore[assignment]
    if not (isinstance(_PortAudioError, type) and issubclass(_PortAudioError, Exception)):
        raise TypeError
except (AttributeError, TypeError):
    _PortAudioError = type("_PortAudioError", (Exception,), {})

SAMPLE_RATE              = 16000
CHANNELS                 = 1
DTYPE                    = "float32"
BLOCK_SIZE               = 1024   # frames per callback
MIN_RECORDING_DURATION   = 0.5    # seconds — shorter recordings are discarded


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Lineer interpolasyonla örnekleme hızı dönüştürür. Konuşma tanıma için yeterli kalite."""
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
    muted_detected     = Signal()        # mathematical 0.0 (muted) detected
    recording_finished = Signal()        # emitted when recording stops (in all cases)
    audio_failed       = Signal()        # recording too short or silent
    mic_unavailable    = Signal()        # hardware unreachable (not found / failed to open / disconnected)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._device_index: int | None = None
        self._chunks: list = []
        self._chunks_lock              = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._intentional_close: bool  = False
        self._native_sr: int           = SAMPLE_RATE
        self._fallback_warned: bool    = False
        # Initially unset (False); calling set() unblocks the thread's wait() and stops it.
        self._stop_event = threading.Event()
        self._silence_timer = QElapsedTimer()
        self._silence_notified = False



    # ------------------------------------------------------------------ QThread
    def run(self):
        """Keeps the thread alive; recording is managed externally via start/stop."""
        self.log_entry.emit("OK", "MIC", "Ready")
        self._stop_event.wait()   # blocks while False; stop() calls set() to unblock

    def stop(self):
        self._stop_event.set()
        self._close_stream()

    # ---------------------------------------------------------- public control
    def set_device(self, device_index: int) -> None:
        if self._device_index == device_index:
            return
            
        self._device_index = device_index
        self._fallback_warned = False
        try:
            name = sd.query_devices(device_index)["name"]
            label = name[:30] + ("…" if len(name) > 30 else "")
        except Exception:
            label = str(device_index)
        self.log_entry.emit("OK", "MIC", f"Device → {label}")

    def refresh_devices(self) -> None:
        """Queries available microphones and reports them via the devices_ready signal."""
        try:
            # PortAudio on Windows caches the device list; a newly plugged-in
            # microphone won't appear. Reinitialise to clear the cache if not recording.
            if self._stream is None:
                sd._terminate()
                sd._initialize()
            all_devices = sd.query_devices()
            default_in  = sd.default.device[0]
            items = []
            for i, dev in enumerate(all_devices):
                if dev["max_input_channels"] > 0:
                    label = dev["name"] + (" (Default)" if i == default_in else "")
                    items.append((label, i, i == default_in))
            self.devices_ready.emit(items)
            if not items:
                self.mic_unavailable.emit()
        except Exception:
            self.log_entry.emit("ERR", "MIC", "Could not retrieve device list")
            self.devices_ready.emit([])
            self.mic_unavailable.emit()

    def start_recording(self):
        if self._stream is not None:
            return  # already recording

        if not self._device_available():
            msg = (
                "No microphone selected." if self._device_index is None
                else "Microphone not found"
            )
            self.log_entry.emit("ERR", "MIC", msg)
            self.error_occurred.emit(msg)
            if self._device_index is not None:
                self.mic_unavailable.emit()
            return

        with self._chunks_lock:
            self._chunks.clear()

        self._intentional_close = False
        self._native_sr = SAMPLE_RATE
        try:
            self._stream = sd.InputStream(
                samplerate       = SAMPLE_RATE,
                channels         = CHANNELS,
                dtype            = DTYPE,
                blocksize        = BLOCK_SIZE,
                device           = self._device_index,
                callback         = self._audio_callback,
                finished_callback= self._on_stream_finished,
            )
            self._stream.start()
            self._silence_timer.invalidate()
            self._silence_notified = False
            self.log_entry.emit("OK", "MIC", "Recording started")
        except _PortAudioError as e:
            # paInvalidDevice (-9996): mic is physically absent; fallback makes no sense.
            if "-9996" in str(e) or "Invalid device" in str(e):
                self._stream = None
                self.log_entry.emit("ERR", "MIC", "Microphone not connected")
                self.error_occurred.emit("Microphone not connected")
                self.mic_unavailable.emit()
                return
            # Device doesn't support 16 kHz; open at native rate and resample in stop_recording.
            try:
                dev_info = sd.query_devices(self._device_index)
                native_sr = int(dev_info["default_samplerate"])
                self._native_sr = native_sr
                self._stream = sd.InputStream(
                    samplerate       = native_sr,
                    channels         = CHANNELS,
                    dtype            = DTYPE,
                    blocksize        = BLOCK_SIZE,
                    device           = self._device_index,
                    callback         = self._audio_callback,
                    finished_callback= self._on_stream_finished,
                )
                self._stream.start()
                if not self._fallback_warned:
                    self.log_entry.emit("...", "MIC", f"Device doesn't support 16kHz, opened at {native_sr}Hz (will auto-resample)")
                    self._fallback_warned = True
            except Exception as e:
                self._stream = None
                self.log_entry.emit("ERR", "MIC", f"Microphone could not be opened: {e}")
                self.error_occurred.emit("Microphone could not be opened")
                self.mic_unavailable.emit()
        except Exception as e:
            self._stream = None
            self.log_entry.emit("ERR", "MIC", f"Microphone could not be opened: {e}")
            self.error_occurred.emit("Microphone could not be opened")
            self.mic_unavailable.emit()

    def stop_recording(self):
        if self._stream is None:
            self.recording_finished.emit()  # count as finished even if there was no stream
            return

        self._close_stream()
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
            if self._native_sr != SAMPLE_RATE:
                audio = _resample(audio, self._native_sr, SAMPLE_RATE)
            duration = len(audio) / SAMPLE_RATE
            if duration < MIN_RECORDING_DURATION:
                self.log_entry.emit("WRN", "MIC", "Recording too short, skipped")
                self.audio_failed.emit()
                return
            if float(np.sqrt(np.mean(audio ** 2))) < 0.001:
                self.log_entry.emit("WRN", "MIC", "Audio too quiet, skipped")
                self.audio_failed.emit()
                return
            self.log_entry.emit("OK", "MIC", f"Recording complete ({duration:.1f}s)")
            self.audio_ready.emit(audio)
        except Exception as e:
            self.log_entry.emit("ERR", "MIC", f"Audio merge error: {e}")
            self.error_occurred.emit("Audio merge error")

    # ----------------------------------------------------------------- private
    def _device_available(self) -> bool:
        """Checks whether the selected device is still present in the system."""
        if self._device_index is None:
            return False
        try:
            device = sd.query_devices(self._device_index)
            return bool(device["max_input_channels"] > 0)
        except Exception:
            return False

    def _audio_callback(self, indata, _frames: int,
                        _time_info, status):
        try:
            if status:
                self.log_entry.emit("WRN", "MIC", f"Status: {status}")

            if indata is not None:
                with self._chunks_lock:
                    self._chunks.append(indata.copy())
                rms = float(np.sqrt(np.mean(indata ** 2)))
                if not np.isfinite(rms):
                    return
                self.level_changed.emit(min(rms * 5.0, 1.0))

                # Mute detection: mathematical 0.0 sustained for > 1500 ms.
                if rms == 0.0:
                    if not self._silence_timer.isValid():
                        self._silence_timer.start()
                    elif self._silence_timer.elapsed() > 1500 and not self._silence_notified:
                        self._silence_notified = True
                        self.muted_detected.emit()
                        # Short beep on a separate thread so the audio callback is not blocked.
                        import threading
                        threading.Thread(
                            target=lambda: (winsound.Beep(440, 100), winsound.Beep(440, 100)),
                            daemon=True
                        ).start()
                else:
                    self._silence_timer.invalidate()
                    self._silence_notified = False
        except Exception:
            self.log_entry.emit("ERR", "MIC", "Audio stream interrupted")

    def _on_stream_finished(self) -> None:
        """Called when the sounddevice stream closes; _intentional_close=False means hardware disconnection."""
        try:
            if self._intentional_close:
                return
            self._stream = None
            self.log_entry.emit("ERR", "MIC", "Connection lost")
            self.error_occurred.emit("Microphone disconnected")
            self.mic_unavailable.emit()
            self.level_changed.emit(0.0)
            self.refresh_devices()  # auto-refresh the device list
        except Exception:
            self.log_entry.emit("ERR", "MIC", "Stream close error")

    def _close_stream(self):
        if self._stream is not None:
            self._intentional_close = True
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                self.log_entry.emit("WRN", "MIC", "Stream could not be closed")
            finally:
                self._stream = None