import sys
from typing import Callable, Any
import numpy as np
import sounddevice as sd

from core.audio_source import AudioSource, AudioDeviceError, AudioDisconnectedError
from core.log import get_logger

_log = get_logger("MIC")

try:
    _PortAudioError: type[Exception] = sd.PortAudioError  # type: ignore[assignment]
    if not (isinstance(_PortAudioError, type) and issubclass(_PortAudioError, Exception)):
        raise TypeError
except (AttributeError, TypeError):
    _PortAudioError = type("_PortAudioError", (Exception,), {})

class PortAudioSource(AudioSource):
    """
    AudioSource implementation using sounddevice (PortAudio).
    """
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1, dtype: str = "float32", block_size: int = 1024):
        self._target_sample_rate = sample_rate
        self._channels = channels
        self._dtype = dtype
        self._block_size = block_size
        
        self._device_index: int | None = None
        self._stream: sd.InputStream | None = None
        self._dead_stream: sd.InputStream | None = None  # ended on its own, not yet closed
        self._intentional_close = False
        self._native_sr = sample_rate
        # (rate, extra_settings) that last opened this device; tried first on the next
        # key press so it opens in one attempt. Memory only, reset on device change.
        self._working: tuple[int, Any] | None = None
        
        self._audio_callback: Callable[[np.ndarray, str | None], None] | None = None
        self._finished_callback: Callable[[Exception | None], None] | None = None

    def set_device(self, device_id: Any) -> str:
        if device_id is None:
            raise AudioDeviceError("No device provided.")
            
        new_index = int(device_id)
        if new_index != self._device_index:
            self._working = None
        self._device_index = new_index
        try:
            name = sd.query_devices(self._device_index)["name"]
            label = name[:30] + ("…" if len(name) > 30 else "")
            return label
        except Exception as e:
            # Revert if unavailable
            self._device_index = None
            raise AudioDeviceError(f"Device query failed: {e}")

    def refresh_devices(self) -> list[tuple[str, Any, bool]]:
        self._close_dead_stream()
        try:
            if self._stream is None:
                sd._terminate()
                sd._initialize()
            all_devices = sd.query_devices()
            default_in  = sd.default.device[0]
            hostapis    = sd.query_hostapis()
            
            if sys.platform == "win32":
                wasapi_idx = next((i for i, h in enumerate(hostapis) if "WASAPI" in h["name"]), None)
            else:
                wasapi_idx = None
                
            items = []
            for i, dev in enumerate(all_devices):
                if dev["max_input_channels"] > 0:
                    if wasapi_idx is not None and dev["hostapi"] != wasapi_idx:
                        continue
                    label = dev["name"] + (" (Default)" if i == default_in else "")
                    items.append((label, i, i == default_in))
            return items
        except Exception:
            return []

    def start(self, 
              audio_callback: Callable[[np.ndarray, str | None], None], 
              finished_callback: Callable[[Exception | None], None]) -> None:
              
        if self._stream is not None:
            return
        self._close_dead_stream()

        if self._device_index is None:
            raise AudioDeviceError("No device selected.")
            
        try:
            device = sd.query_devices(self._device_index)
            if not (device["max_input_channels"] > 0):
                raise AudioDeviceError("Device has no input channels.")
        except Exception:
            raise AudioDeviceError("Microphone not found.")

        self._audio_callback = audio_callback
        self._finished_callback = finished_callback
        self._intentional_close = False

        attempts = self._open_attempts(int(device["default_samplerate"]))
        last_error: Exception | None = None
        for rate, extra in attempts:
            stream = None
            try:
                stream = sd.InputStream(
                    samplerate       = rate,
                    channels         = self._channels,
                    dtype            = self._dtype,
                    blocksize        = self._block_size,
                    device           = self._device_index,
                    callback         = self._sd_audio_callback,
                    finished_callback= self._sd_finished_callback,
                    extra_settings   = extra,
                )
                self._stream = stream
                stream.start()
            except Exception as e:
                self._stream = None
                if stream is not None:
                    try:
                        stream.close()  # created but failed to start: do not leak it
                    except Exception:
                        pass
                if isinstance(e, _PortAudioError) and ("-9996" in str(e) or "Invalid device" in str(e)):
                    raise AudioDeviceError("Microphone not connected")
                last_error = e
                continue
            self._native_sr = rate
            if (rate, extra) != attempts[0]:
                _log.info(f"Microphone opened at {rate} Hz")
            self._working = (rate, extra)
            return
        raise AudioDeviceError(f"Microphone could not be opened: {last_error}")

    def _open_attempts(self, native_rate: int) -> list[tuple[int, Any]]:
        """Open settings to try, best first (plan 0006). WASAPI shared mode rejects 16 kHz
        unless asked to convert; a remembered working setting skips the failed tries."""
        attempts: list[tuple[int, Any]] = []
        if self._working is not None:
            attempts.append(self._working)
        if sys.platform == "win32":
            try:
                attempts.append((self._target_sample_rate, sd.WasapiSettings(auto_convert=True)))
            except Exception:
                pass  # older sounddevice without auto_convert: fall through to the plain tries
        attempts.append((self._target_sample_rate, None))
        if native_rate != self._target_sample_rate:
            attempts.append((native_rate, None))
        unique: list[tuple[int, Any]] = []
        for attempt in attempts:
            if attempt not in unique:
                unique.append(attempt)
        return unique

    def stop(self) -> None:
        self._close_dead_stream()
        stream = self._stream
        if stream is not None:
            self._intentional_close = True
            # The finished callback may run inside stream.stop() and set
            # self._stream = None; hold our own reference so close() still runs.
            self._stream = None
            try:
                stream.stop()
                stream.close()
            except Exception as e:
                _log.warning(f"Microphone stream did not close cleanly: {e}")

    @property
    def native_sample_rate(self) -> int:
        return self._native_sr

    def _sd_audio_callback(self, indata, frames, time_info, status):
        if self._audio_callback:
            status_msg = str(status) if status else None
            if indata is not None:
                self._audio_callback(indata.copy(), status_msg)

    def _close_dead_stream(self) -> None:
        """Closes a stream that ended on its own. PortAudio forbids closing a stream
        from its own callback, so this runs on the next call from the owning thread."""
        if self._dead_stream is not None:
            try:
                self._dead_stream.close()
            except Exception:
                pass
            self._dead_stream = None

    def _sd_finished_callback(self) -> None:
        # Runs on PortAudio's thread: only record state and notify here.
        if self._intentional_close:
            err = None
        else:
            err = AudioDisconnectedError("Stream closed unexpectedly.")
            self._dead_stream = self._stream

        self._stream = None
        if self._finished_callback:
            self._finished_callback(err)
