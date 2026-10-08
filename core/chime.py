"""The two soft tones that mark the start and the end of a dictation.

Hands-free, nothing is held down, so the ear has to be told that Katib is listening and
that it has stopped. The tones are made here: no sound files to ship.
"""
import io
import sys
import threading
import wave

import numpy as np

_RATE = 44100


def _tone(frequencies: tuple[float, ...], seconds: float = 0.11, volume: float = 0.09) -> bytes:
    """Short sine notes, one after the other, as a WAV file in memory."""
    t = np.arange(int(_RATE * seconds)) / _RATE
    envelope = np.sin(np.pi * t / seconds) ** 2  # every note fades in and out: soft, no click
    notes = [np.sin(2 * np.pi * frequency * t) * envelope for frequency in frequencies]
    pcm = (np.concatenate(notes) * volume * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_RATE)
        w.writeframes(pcm.tobytes())
    return buffer.getvalue()


# Rising, falling. Quiet and low on purpose: heard, never startling.
_SOUNDS = {"start": _tone((523.0, 659.0)), "end": _tone((659.0, 523.0))}


def _play(data: bytes) -> None:
    if sys.platform != "win32":
        return
    try:
        import winsound
        winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
    except Exception:
        pass  # no output device: a missing tone is not an error


def chime(kind: str) -> None:
    """Plays "start" or "end" without blocking the caller."""
    threading.Thread(target=_play, args=(_SOUNDS[kind],), daemon=True).start()
