"""core.segmenter (plan 0014): where a long dictation may be cut while it is still spoken."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from core.segmenter import (CONTEXT_CHARS, END_PAUSE_SECONDS, NO_SPEECH_SECONDS, context_prompt,
                            find_cut, first_sentence, next_cut, same_words, speech_is_over)

SR = 16000


class TestFirstSentence:
    """Words as the model gives them: each with its own leading space, or none."""

    WORDS = [(" Bugün", 0.4), (" geldim.", 1.1), (" Yarın", 1.6), (" e", 1.8), ("-posta", 2.3), (" yazarım.", 3.0)]

    def test_ends_at_the_first_word_that_closes_a_sentence(self):
        assert first_sentence(self.WORDS) == ("Bugün geldim.", 1.1, 2)

    def test_the_rest_can_be_asked_again(self):
        assert first_sentence(self.WORDS[2:]) is None   # its full stop is on the last word

    def test_words_are_joined_as_the_model_spaced_them(self):
        words = self.WORDS[2:] + [(" Sonra", 3.4)]
        assert first_sentence(words) == ("Yarın e-posta yazarım.", 3.0, 4)

    def test_the_last_word_never_closes_a_sentence(self):
        """The model ends whatever audio it is given with a full stop or "..." of its own."""
        assert first_sentence([(" Bugün", 0.4), (" geldim.", 1.1)]) is None
        assert first_sentence([(" Bugün", 0.4), (" geldim...", 1.1)]) is None

    def test_question_and_exclamation_marks_close_one_too(self):
        assert first_sentence([(" Geldin", 0.4), (" mi?", 0.8), (" Evet", 1.2)]) == ("Geldin mi?", 0.8, 2)
        assert first_sentence([(" Harika!", 0.5), (" Devam", 1.0)]) == ("Harika!", 0.5, 1)

    def test_a_decimal_point_inside_a_word_is_not_an_end(self):
        assert first_sentence([(" Sürüm", 0.4), (" 1.2", 0.9), (" çıktı", 1.3)]) is None

    def test_nothing_heard(self):
        assert first_sentence([]) is None


class TestSameWords:
    def test_capitals_and_punctuation_do_not_matter(self):
        assert same_words("Bugün geldim.", "bugün, geldim!")

    def test_the_dotted_capital_i_at_the_start_of_a_turkish_sentence_matches(self):
        """A sentence starts with "İndirme" in one pass and continues with "indirme" in another."""
        assert same_words("İndirme tamam.", "indirme tamam.")

    def test_a_different_word_matters(self):
        assert not same_words("Gösterge görüntülenecek.", "Gösterge düzgün çalışıyor.")

    def test_a_missing_word_matters(self):
        assert not same_words("Bugün geldim.", "Bugün ben geldim.")


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


class TestSpeechIsOver:
    """Hands-free dictation: when has the speaker finished?"""

    def test_speech_running_to_the_end_is_not_over(self):
        assert not speech_is_over([_chunk(0, 5)], 5 * SR)

    def test_a_thinking_pause_is_not_the_end(self):
        assert not speech_is_over([_chunk(0, 5)], int((5 + END_PAUSE_SECONDS - 0.5) * SR))

    def test_a_long_silence_after_speech_is_the_end(self):
        assert speech_is_over([_chunk(0, 5)], int((5 + END_PAUSE_SECONDS) * SR))

    def test_silence_at_the_start_waits_for_the_speaker(self):
        assert not speech_is_over([], int((NO_SPEECH_SECONDS - 1) * SR))

    def test_nothing_said_at_all_is_the_end(self):
        assert speech_is_over([], int(NO_SPEECH_SECONDS * SR))

    def test_silence_after_a_piece_already_cut_off_is_the_end(self):
        assert speech_is_over([], int(END_PAUSE_SECONDS * SR), heard_before=True)
        assert not speech_is_over([], int((END_PAUSE_SECONDS - 1) * SR), heard_before=True)


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
