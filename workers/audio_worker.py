import threading
import sys
import numpy as np
from PySide6.QtCore import Qt, Signal, QElapsedTimer

from workers.base_worker import BaseWorker, measure_time
from core.log import get_logger, OK
from core.audio_source import AudioSource, AudioDeviceError, AudioDisconnectedError

_log = get_logger("MIC")

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
    muted_detected     = Signal()        # mathematical 0.0 (muted) detected
    audio_failed       = Signal()        # recording too short or silent
    # What was heard, for the settings window: seconds, speech dB, noise-floor dB, and the
    # i18n key of the reason it was dropped ("" when it went on to be transcribed).
    recording_analysed = Signal(float, float, float, str)
    mic_unavailable    = Signal()        # hardware unreachable (not found / failed to open / disconnected)
    _stream_lost       = Signal()        # private: hop from the PortAudio thread to this object's thread

    def __init__(self, settings, audio_source: AudioSource, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.audio_source = audio_source
        
        self._device_index: int | None = None
        self._chunks: list = []
        self._rms_history: list = []
        self._chunks_lock              = threading.Lock()
        
        # Keep track if we are actively recording.
        self._is_recording = False
        
        # Initially unset (False); calling set() unblocks the thread's wait() and stops it.
        self._stop_event = threading.Event()
        self._silence_timer = QElapsedTimer()
        self._silence_notified = False
        self._start_clock = QElapsedTimer()  # start_recording() → first audio chunk (plan 0006)
        self._first_chunk_pending = False

        # refresh_devices() re-initialises PortAudio, which must not happen inside a
        # PortAudio callback; the queued connection defers it until the callback returns.
        self._stream_lost.connect(self.refresh_devices, Qt.ConnectionType.QueuedConnection)

        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._init_media_devices)

    def _init_media_devices(self):
        from PySide6.QtMultimedia import QMediaDevices
        from PySide6.QtCore import QTimer
        self._media_devices = QMediaDevices(self)
        self._media_devices.audioInputsChanged.connect(self._on_audio_inputs_changed)
        
        # Debounce: hardware events (plug/unplug) can fire dozens of times per second.
        self._device_refresh_timer = QTimer(self)
        self._device_refresh_timer.setSingleShot(True)
        self._device_refresh_timer.setInterval(500)
        self._device_refresh_timer.timeout.connect(self._do_audio_inputs_changed)

    def _on_audio_inputs_changed(self) -> None:
        if hasattr(self, "_device_refresh_timer"):
            self._device_refresh_timer.start()
        else:
            self._do_audio_inputs_changed()

    def _do_audio_inputs_changed(self) -> None:
        _log.info("Hardware change detected, refreshing devices...")
        self.refresh_devices()

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
            _log.log(OK, f"Device → {label}")
        except AudioDeviceError as e:
            _log.error(f"Device error: {e}")
            self._device_index = None

    @measure_time("MIC", "Device refresh (UI thread)")
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
            _log.error("No microphone selected.")
            self.error_occurred.emit("osd.mic_no_device")
            return

        with self._chunks_lock:
            self._chunks.clear()
            self._rms_history.clear()

        try:
            self._start_clock.start()
            self._first_chunk_pending = True
            self.audio_source.start(self._audio_callback, self._on_stream_finished)
            self._is_recording = True
            self._silence_timer.invalidate()
            self._silence_notified = False
            _log.log(OK, "Recording started")
        except AudioDeviceError as e:
            msg = str(e)
            if "not connected" in msg.lower():
                _log.error("Microphone not connected")
                self.error_occurred.emit("osd.mic_not_connected")
            else:
                _log.error(f"Microphone could not be opened: {e}")
                self.error_occurred.emit("osd.mic_open_failed")
            self.mic_unavailable.emit()
            self._is_recording = False
        except Exception as e:
            _log.error(f"Microphone could not be opened: {e}")
            self.error_occurred.emit("osd.mic_open_failed")
            self.mic_unavailable.emit()
            self._is_recording = False

    @measure_time("MIC", "Stop recording (UI thread)")
    def stop_recording(self):
        if not self._is_recording:
            return

        self.audio_source.stop()
        self._is_recording = False
        
        self.level_changed.emit(0.0)

        with self._chunks_lock:
            chunks_snapshot = list(self._chunks)
            self._chunks.clear()

        if not chunks_snapshot:
            _log.warning("Recording is empty")
            self.recording_analysed.emit(0.0, -120.0, -120.0, "osd.recording_too_short")
            self.audio_failed.emit()
            return

        try:
            audio = np.concatenate(chunks_snapshot, axis=0).flatten()
            native_sr = self.audio_source.native_sample_rate
            if native_sr != SAMPLE_RATE:
                audio = _resample(audio, native_sr, SAMPLE_RATE)

            duration = len(audio) / SAMPLE_RATE
            from core.audio_analysis import analyse_vad, is_silent
            chunk_duration = len(audio) / SAMPLE_RATE / len(self._rms_history) if self._rms_history else 0.1
            stats = analyse_vad(self._rms_history, chunk_duration)

            def report(problem: str) -> None:
                self.recording_analysed.emit(duration, stats["speech_db"], stats["noise_db"], problem)

            if duration < MIN_RECORDING_DURATION:
                _log.warning("Recording too short, skipped")
                report("osd.recording_too_short")
                self.audio_failed.emit()
                return

            if is_silent(stats):
                _log.warning(f"Audio discarded as silence/noise (Noise floor: {stats['noise_db']:.1f} dB, Speech peak: {stats['speech_db']:.1f} dB, Voiced: {stats['voiced_seconds']:.2f}s)")
                self.error_occurred.emit("osd.audio_too_quiet")
                report("osd.audio_too_quiet")
                self.audio_failed.emit()
                return

            _log.log(OK, f"Recording complete ({duration:.1f}s)")
            report("")
            self.audio_ready.emit(audio)
        except Exception as e:
            _log.error(f"Audio merge error: {e}")
            self.error_occurred.emit("osd.audio_merge_error")

    # ----------------------------------------------------------------- private

    def _audio_callback(self, indata: np.ndarray, status_msg: str | None):
        try:
            if status_msg:
                _log.warning(f"Status: {status_msg}")

            if self._first_chunk_pending:
                self._first_chunk_pending = False
                _log.log(OK, f"First audio after {self._start_clock.elapsed()} ms")

            if indata is not None:
                rms = float(np.sqrt(np.mean(indata ** 2)))
                if not np.isfinite(rms):
                    return
                
                with self._chunks_lock:
                    self._chunks.append(indata)  # already the receiver's own copy (AudioSource contract)
                    self._rms_history.append(rms)

                self.level_changed.emit(min(rms * 5.0, 1.0))

                # Mute detection: mathematical 0.0 sustained for > 1500 ms.
                if rms == 0.0:
                    if not self._silence_timer.isValid():
                        self._silence_timer.start()
                    elif self._silence_timer.elapsed() > 1500 and not self._silence_notified:
                        self._silence_notified = True
                        _log.error("Microphone muted (signal is exactly zero)")
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
            _log.error("Audio stream interrupted")

    def _on_stream_finished(self, err: Exception | None) -> None:
        """Called when the stream closes. If err is not None, it closed unexpectedly."""
        self._is_recording = False
        try:
            if err is None:
                return # Intentional close
                
            _log.error("Connection lost")
            self.error_occurred.emit("osd.mic_disconnected")
            self.mic_unavailable.emit()
            self.level_changed.emit(0.0)
            self._stream_lost.emit()  # auto-refresh the device list on the main thread
        except Exception:
            _log.error("Stream close error")