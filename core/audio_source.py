from abc import ABC, abstractmethod
from typing import Callable, Any
import numpy as np

class AudioSourceError(Exception):
    """Base class for exceptions raised by AudioSource implementations."""
    pass

class AudioDeviceError(AudioSourceError):
    """Raised when a specific audio device cannot be opened or is missing."""
    pass

class AudioDisconnectedError(AudioSourceError):
    """Raised when an active audio stream is unexpectedly disconnected."""
    pass


class AudioSource(ABC):
    """
    Interface for providing a continuous audio stream.
    """
    
    @abstractmethod
    def set_device(self, device_id: Any) -> str:
        """
        Sets the active device and returns its human-readable label.
        """
        pass

    @abstractmethod
    def refresh_devices(self) -> list[tuple[str, Any, bool]]:
        """
        Returns a list of available devices as (label, id, is_default).
        """
        pass

    @abstractmethod
    def start(self, 
              audio_callback: Callable[[np.ndarray, str | None], None], 
              finished_callback: Callable[[Exception | None], None]) -> None:
        """
        Starts the audio stream.
        
        Args:
            audio_callback: Called with (audio_chunk, status_message) for each incoming block.
            finished_callback: Called when the stream closes. If it closed unexpectedly, 
                               an exception (like AudioDisconnectedError) is passed.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops the audio stream safely."""
        pass
        
    @property
    @abstractmethod
    def native_sample_rate(self) -> int:
        """Returns the native sample rate of the current stream."""
        pass
