"""core.segmenter (plan 0014): where a long dictation may be cut while it is still spoken."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from core.segmenter import CONTEXT_CHARS, context_prompt, find_cut, next_cut

SR = 16000


def _chunk(start_s: float, end_s: float) -> dict:
    return {"start": int(start_s * SR), "end": int(end_s * SR)}


class TestNextCut:
    def test_no_speech_means_no_cut(self):
        assert next_cut([], 20 * SR) is None

    def test_a_pause_before_enough_speech_is_not_a_cut(self):
        # 5 s of speech, 1 s pause, more speech: the first piece would be too short
        assert next_cut([_chunk(0, 5), _chunk(6, 12)], 12 * SR) is None

    def test_a_pause_after_enough_speech_is_cut_in_its_middle(self):
        cut = next_cut([_chunk(0, 9), _chunk(10, 14)], 14 * SR)
        assert cut == int(9.5 * SR)

    def test_a_short_breath_is_not_a_cut(self):
        assert next_cut([_chunk(0, 9), _chunk(9.3, 14)], 14 * SR) is None

    def test_the_first_suitable_pause_wins(self):
        speeches = [_chunk(0, 3), _chunk(4, 9), _chunk(10, 15), _chunk(16, 20)]
        assert next_cut(speeches, 20 * SR) == int(9.5 * SR)

    def test_silence_after_the_last_chunk_counts(self):
        # the speaker stopped at 10 s and the key is still held
        assert next_cut([_chunk(0, 10)], 11 * SR) == int(10.5 * SR)

    def test_speech_running_to_the_end_is_not_cut(self):
        assert next_cut([_chunk(0, 12)], 12 * SR) is None

    def test_the_minimums_can_be_given(self):
        speeches = [_chunk(0, 2), _chunk(2.5, 4)]
        assert next_cut(speeches, 4 * SR, min_segment_seconds=1, min_pause_seconds=0.4) == int(2.25 * SR)


class TestFindCut:
    def test_vad_runs_unpadded_with_the_pause_length_and_given_threshold(self):
        # A stand-in module: other test files replace faster_whisper with a MagicMock.
        vad = MagicMock(return_value=[_chunk(0, 9)])
        fake = SimpleNamespace(VadOptions=lambda **kw: SimpleNamespace(**kw), get_speech_timestamps=vad)
        audio = np.zeros(12 * SR, dtype=np.float32)
        with patch.dict(sys.modules, {"faster_whisper.vad": fake}):
            cut = find_cut(audio, threshold=0.4)
        options = vad.call_args[0][1]
        assert (options.threshold, options.speech_pad_ms, options.min_silence_duration_ms) == (0.4, 0, 700)
        assert cut == int(10.5 * SR)  # the pause from 9 s to the end of the 12 s


class TestContextPrompt:
    def test_user_prompt_then_the_text_so_far(self):
        assert context_prompt("Katib, ADR.", "Toplantı bitti.") == "Katib, ADR. Toplantı bitti."

    def test_nothing_so_far_is_just_the_user_prompt(self):
        assert context_prompt("  Katib  ", "") == "Katib"
        assert context_prompt("", "") == ""

    def test_only_the_end_is_kept_and_the_user_prompt_survives(self):
        text = "kelime " * 100 + "son"
        prompt = context_prompt("Katib", text)
        assert prompt.startswith("Katib ") and prompt.endswith("son")
        assert len(prompt) == len("Katib ") + CONTEXT_CHARS
