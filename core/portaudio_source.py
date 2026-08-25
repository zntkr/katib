import sys
from typing import Callable, Any
import numpy as np
import sounddevice as sd

from core.audio_source import AudioSource, AudioDeviceError, AudioDisconnectedError

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
        self._intentional_close = False
        self._native_sr = sample_rate
        
        self._audio_callback: Callable[[np.ndarray, str | None], None] | None = None
        self._finished_callback: Callable[[Exception | None], None] | None = None

    def set_device(self, device_id: Any) -> str:
        if device_id is None:
            raise AudioDeviceError("No device provided.")
            
        self._device_index = int(device_id)
        try:
            name = sd.query_devices(self._device_index)["name"]
            label = name[:30] + ("…" if len(name) > 30 else "")
            return label
        except Exception as e:
            # Revert if unavailable
            self._device_index = None
            raise AudioDeviceError(f"Device query failed: {e}")

    def refresh_devices(self) -> list[tuple[str, Any, bool]]:
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
        self._native_sr = self._target_sample_rate
        
        try:
            self._stream = sd.InputStream(
                samplerate       = self._target_sample_rate,
                channels         = self._channels,
                dtype            = self._dtype,
                blocksize        = self._block_size,
                device           = self._device_index,
                callback         = self._sd_audio_callback,
                finished_callback= self._sd_finished_callback,
            )
            self._stream.start()
        except _PortAudioError as e:
            if "-9996" in str(e) or "Invalid device" in str(e):
                self._stream = None
                raise AudioDeviceError("Microphone not connected")
                
            # Fallback to native sample rate
            try:
                dev_info = sd.query_devices(self._device_index)
                self._native_sr = int(dev_info["default_samplerate"])
                self._stream = sd.InputStream(
                    samplerate       = self._native_sr,
                    channels         = self._channels,
                    dtype            = self._dtype,
                    blocksize        = self._block_size,
                    device           = self._device_index,
                    callback         = self._sd_audio_callback,
                    finished_callback= self._sd_finished_callback,
                )
                self._stream.start()
            except Exception as inner_e:
                self._stream = None
                raise AudioDeviceError(f"Microphone could not be opened: {inner_e}")
        except Exception as e:
            self._stream = None
            raise AudioDeviceError(f"Microphone could not be opened: {e}")

    def stop(self) -> None:
        if self._stream is not None:
            self._intentional_close = True
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            finally:
                self._stream = None

    @property
    def native_sample_rate(self) -> int:
        return self._native_sr

    def _sd_audio_callback(self, indata, frames, time_info, status):
        if self._audio_callback:
            status_msg = str(status) if status else None
            if indata is not None:
                self._audio_callback(indata.copy(), status_msg)

    def _sd_finished_callback(self) -> None:
        if self._intentional_close:
            err = None
        else:
            err = AudioDisconnectedError("Stream closed unexpectedly.")
        
        self._stream = None
        if self._finished_callback:
            self._finished_callback(err)
