import wave
import threading
import time
from typing import Callable, Any
import numpy as np

from core.audio_source import AudioSource, AudioDeviceError

class WavFileSource(AudioSource):
    """
    Simulates a microphone using a .wav file.
    """
    def __init__(self, filepath: str, block_size: int = 1024, real_time: bool = False):
        self.filepath = filepath
        self.block_size = block_size
        self.real_time = real_time
        
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._native_sr = 16000
        
        self._audio_callback: Callable[[np.ndarray, str | None], None] | None = None
        self._finished_callback: Callable[[Exception | None], None] | None = None

    def set_device(self, device_id: Any) -> str:
        return f"WavFile: {self.filepath}"

    def refresh_devices(self) -> list[tuple[str, Any, bool]]:
        return [(f"WavFile: {self.filepath}", self.filepath, True)]

    def start(self, 
              audio_callback: Callable[[np.ndarray, str | None], None], 
              finished_callback: Callable[[Exception | None], None]) -> None:
        self._audio_callback = audio_callback
        self._finished_callback = finished_callback
        self._stop_event.clear()
        
        try:
            with wave.open(self.filepath, 'rb') as wf:
                self._native_sr = wf.getframerate()
        except Exception as e:
            raise AudioDeviceError(f"Cannot open wav file: {e}")
            
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    @property
    def native_sample_rate(self) -> int:
        return self._native_sr

    def _run(self):
        try:
            with wave.open(self.filepath, 'rb') as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                
                while not self._stop_event.is_set():
                    raw_data = wf.readframes(self.block_size)
                    if not raw_data:
                        break # EOF
                        
                    if sampwidth == 2:
                        data = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                    else:
                        data = np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32) / 255.0 - 0.5
                        data *= 2.0
                        
                    if channels > 1:
                        data = data.reshape(-1, channels).mean(axis=1) # mix to mono
                        
                    if self._audio_callback:
                        self._audio_callback(data, None)
                        
                    if self.real_time:
                        time.sleep(self.block_size / self._native_sr)
                        
        except Exception:
            pass # ignore read errors
            
        if self._finished_callback:
            self._finished_callback(None)
