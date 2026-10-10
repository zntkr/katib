"""Where a long dictation can be cut while it is still being spoken (plan 0014).

A finished stretch of speech can be transcribed in the background while the user keeps
talking; on key release only the rest is left. A cut goes only into a real pause, and only
after enough speech that the extra 30 s encoder pass of a separate piece is worth it.

next_cut() is pure (speech chunks in, a sample index out); find_cut() runs Silero VAD on
the audio first. The worker and scripts/olcum.py use the same functions, so what is
measured is what runs.
"""
import numpy as np

SAMPLE_RATE = 16000
MIN_SEGMENT_SECONDS = 8.0   # a piece is at least this long before it may be cut off
# Hands-free on the GPU, where the extra encoder pass of a piece costs 0.2-0.4 s, not seconds:
# a sentence is typed at its first real pause. Below this Whisper is unreliable.
MIN_SEGMENT_SECONDS_FAST = 1.5
# Same mode, speech that goes on without a pause: the model is asked where a sentence ends
# once this much is waiting. Less than a sentence and the start of the next is no use to it.
SENTENCE_PASS_SECONDS = 3.0
MIN_PAUSE_SECONDS = 0.7     # only a pause at least this long is a cut point
CONTEXT_CHARS = 200         # how much of the text so far the next piece is prompted with
END_PAUSE_SECONDS = 3.0     # hands-free: this much silence after speech ends the dictation
NO_SPEECH_SECONDS = 8.0     # hands-free: nothing said for this long ends it too


def next_cut(speeches: list[dict], length: int, sample_rate: int = SAMPLE_RATE,
             min_segment_seconds: float = MIN_SEGMENT_SECONDS,
             min_pause_seconds: float = MIN_PAUSE_SECONDS) -> int | None:
    """The sample index to cut at: the middle of the first pause of at least
    min_pause_seconds that starts at least min_segment_seconds into the audio.
    None when there is no such pause yet.

    speeches: VAD speech chunks [{"start": int, "end": int}, ...] in samples, sorted,
    unpadded; length: samples of audio they were found in. Silence after the last chunk
    counts as a pause too: the speaker has stopped, possibly for good.
    """
    if not speeches:
        return None
    min_segment = min_segment_seconds * sample_rate
    min_pause = min_pause_seconds * sample_rate
    gaps = [(a["end"], b["start"]) for a, b in zip(speeches, speeches[1:])]
    gaps.append((speeches[-1]["end"], length))
    for pause_start, pause_end in gaps:
        if pause_start >= min_segment and pause_end - pause_start >= min_pause:
            return (pause_start + pause_end) // 2
    return None


SENTENCE_ENDS = (".", "!", "?", "…")


def first_sentence(words: list[tuple[str, float]]) -> tuple[str, float, int] | None:
    """The first finished sentence in what the model heard: (its text, the second it ends at,
    how many words it has). words: [(text, end_seconds), ...] in order, each text as the
    model gives it, with its own leading space or none ("e", "-posta"). A sentence is
    finished when a word ends it and another word follows; the last word never counts, the
    model closes whatever it was given with a full stop or "..." of its own.

    The model's own segments cannot be used for this: on speech without pauses it returned
    everything waiting as one segment for 30 s (measured 2026-10-10)."""
    for i, (text, end) in enumerate(words[:-1]):
        if text.rstrip().endswith(SENTENCE_ENDS):
            return "".join(word for word, _ in words[: i + 1]).strip(), end, i + 1
    return None


def same_words(a: str, b: str) -> bool:
    """Two passes over the same speech agree: same words in the same order. Capitals and
    punctuation are left out, they flip between passes without the words changing."""
    def bare(text: str) -> list[str]:
        return ["".join(ch for ch in word.casefold() if ch.isalnum()) for word in text.split()]
    return bare(a) == bare(b)


def speech_is_over(speeches: list[dict], length: int, heard_before: bool = False,
                   sample_rate: int = SAMPLE_RATE) -> bool:
    """Hands-free dictation: has the speaker finished? True after END_PAUSE_SECONDS of
    silence following speech, or when nothing was said for NO_SPEECH_SECONDS.

    heard_before: speech was already cut off this audio, so silence alone means "finished".
    """
    if speeches:
        return length - speeches[-1]["end"] >= END_PAUSE_SECONDS * sample_rate
    return length >= (END_PAUSE_SECONDS if heard_before else NO_SPEECH_SECONDS) * sample_rate


def speech_chunks(audio: np.ndarray, threshold: float = 0.4) -> list[dict]:
    """Silero VAD's view of the audio (16 kHz mono float32): where speech is, in samples."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    options = VadOptions(
        threshold=threshold,
        min_silence_duration_ms=int(MIN_PAUSE_SECONDS * 1000),  # shorter silences stay inside a chunk
        speech_pad_ms=0,  # chunk edges are where speech is, so the gaps are the real pauses
    )
    return get_speech_timestamps(audio, options)


def find_cut(audio: np.ndarray, threshold: float = 0.4) -> int | None:
    """next_cut() on Silero VAD's view of the audio."""
    return next_cut(speech_chunks(audio, threshold), len(audio))


def context_prompt(user_prompt: str, text_so_far: str, max_chars: int = CONTEXT_CHARS) -> str:
    """The prompt for the next piece: the user's own prompt, then the end of what was
    already transcribed, so capitalisation, punctuation and terms carry over the cut."""
    # faster-whisper keeps only the last ~223 prompt tokens; an uncut text would push the
    # user's prompt, which comes first, out of them.
    tail = text_so_far.strip()[-max_chars:]
    return " ".join(part for part in (user_prompt.strip(), tail) if part)
