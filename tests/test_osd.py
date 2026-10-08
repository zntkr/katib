"""The pill (ui/osd.py): what it shows while recording, while the model works and for a
message, and the level wave inside it."""
from unittest.mock import patch

import pytest

from ui.osd import LevelWave, MinimalOSD, loudness
from ui.theme import theme_manager


def _settle(wave: LevelWave, frames: int = 60) -> None:
    for _ in range(frames):
        wave.advance()


@pytest.fixture
def osd(qapp):
    widget = MinimalOSD()
    with patch.object(widget, "position_osd"):  # keep the pill where it is during tests
        yield widget
    widget.close()
    widget.deleteLater()


@pytest.fixture
def wave(qapp):
    widget = LevelWave()
    widget.set_mode("level", theme_manager.palette["CLR_ERR"])
    yield widget
    widget.deleteLater()


class TestLoudness:
    """The worker reports rms × 5, capped at 1. The wave shows it on a dB scale so a quiet
    microphone still moves: −60 dB is silence, −10 dB is full height."""

    def test_silence_is_zero(self):
        assert loudness(0.0) == 0.0

    def test_a_quiet_microphone_is_still_visible(self):
        assert 0.15 < loudness(0.0035 * 5) < 0.35      # rms −49 dB, the weak headset of 2026-10-03

    def test_normal_speech_is_well_up(self):
        assert 0.6 < loudness(0.05 * 5) < 0.8          # rms −26 dB

    def test_the_cap_is_near_the_top(self):
        assert loudness(1.0) > 0.9

    def test_louder_is_never_lower(self):
        values = [loudness(level / 100) for level in range(0, 101)]
        assert values == sorted(values)

    def test_stays_between_zero_and_one(self):
        assert loudness(-3.0) == 0.0
        assert loudness(50.0) == 1.0


class TestLevelWave:
    def test_starts_flat(self, wave):
        assert wave.bars == [0.0] * LevelWave.BARS

    def test_a_level_rises_at_the_right_edge(self, wave):
        wave.push_level(0.25)
        _settle(wave)
        assert wave.bars[-1] == pytest.approx(loudness(0.25), abs=0.01)
        assert wave.bars[:-1] == pytest.approx([0.0] * (LevelWave.BARS - 1), abs=0.01)

    def test_older_levels_move_left(self, wave):
        wave.push_level(1.0)
        wave.push_level(0.0)
        _settle(wave)
        assert wave.bars[-2] == pytest.approx(loudness(1.0), abs=0.01)
        assert wave.bars[-1] == pytest.approx(0.0, abs=0.01)

    def test_the_oldest_level_drops_off_the_left_edge(self, wave):
        wave.push_level(1.0)
        for _ in range(LevelWave.BARS):
            wave.push_level(0.0)
        _settle(wave)
        assert max(wave.bars) == pytest.approx(0.0, abs=0.01)

    def test_bars_ease_towards_the_level(self, wave):
        wave.push_level(1.0)
        wave.advance()
        assert 0.0 < wave.bars[-1] < loudness(1.0)

    def test_busy_mode_moves_by_itself(self, wave):
        wave.set_mode("busy", theme_manager.palette["CLR_INFO"])
        _settle(wave, 10)
        first = list(wave.bars)
        _settle(wave, 5)
        assert wave.bars != first
        assert len(set(round(bar, 3) for bar in wave.bars)) > 1   # a wave, not a flat block

    def test_busy_mode_ignores_the_microphone(self, wave):
        wave.set_mode("busy", theme_manager.palette["CLR_INFO"])
        wave.push_level(1.0)
        _settle(wave)
        assert max(wave.bars) < 0.9

    def test_changing_mode_starts_from_flat(self, wave):
        wave.push_level(1.0)
        _settle(wave)
        wave.set_mode("dot", theme_manager.palette["CLR_WARN"])
        assert wave.bars == [0.0] * LevelWave.BARS

    @pytest.mark.parametrize("mode", ["level", "busy", "dot"])
    def test_paints_in_every_mode(self, wave, mode):
        wave.set_mode(mode, theme_manager.palette["CLR_ERR"])
        wave.push_level(0.5)
        _settle(wave, 5)
        assert not wave.grab().isNull()


class TestRecording:
    def test_shows_the_level_wave_in_the_recording_colour(self, osd):
        osd.setStateRecording()
        assert osd.wave.mode == "level"
        assert osd.wave.colour.name() == theme_manager.palette["CLR_ERR"].lower()
        assert osd.text_label.isHidden()  # the wave says it; no words
        assert osd.wave_timer.isActive()
        assert osd.isVisible()

    def test_the_microphone_level_moves_the_wave(self, osd):
        osd.setStateRecording()
        osd.update_level(0.5)
        _settle(osd.wave)
        assert osd.wave.bars[-1] == pytest.approx(loudness(0.5), abs=0.01)

    def test_a_new_recording_starts_with_a_flat_wave(self, osd):
        osd.setStateRecording()
        osd.update_level(1.0)
        _settle(osd.wave)
        osd.setStateRecording()
        assert osd.wave.bars == [0.0] * LevelWave.BARS

    def test_level_is_kept_within_bounds(self, osd):
        osd.update_level(-5.0)
        assert osd.current_level == 0.0
        osd.update_level(10.0)
        assert osd.current_level == 1.0


class TestProcessing:
    def test_shows_a_moving_wave_in_the_info_colour(self, osd):
        osd.setStateRecording()
        osd.setStateProcessing()
        assert osd.wave.mode == "busy"
        assert osd.wave.colour.name() == theme_manager.palette["CLR_INFO"].lower()
        assert osd.text_label.isHidden()
        assert osd.wave_timer.isActive()

    def test_the_pill_is_only_as_wide_as_the_wave(self, osd):
        osd.setStateProcessing()
        without_words = osd.width()
        osd.setStateError("osd.mic_muted")
        assert not osd.text_label.isHidden() and osd.width() > without_words
        osd._error_active = False
        osd.setStateRecording()
        assert osd.width() == without_words

    def test_late_microphone_levels_do_not_disturb_it(self, osd):
        osd.setStateProcessing()
        osd.update_level(1.0)
        _settle(osd.wave)
        assert max(osd.wave.bars) < 0.9


class TestMessage:
    def test_shows_a_still_dot_and_the_text_in_capitals(self, osd):
        osd.setStateRecording()
        osd.setStateError("test error")
        assert osd.wave.mode == "dot"
        assert osd.wave.colour.name() == theme_manager.palette["CLR_WARN"].lower()
        assert osd.text_label.text() == "TEST ERROR"
        assert not osd.wave_timer.isActive()

    def test_translates_a_known_key(self, osd):
        osd.setStateError("osd.mic_muted")
        assert osd.text_label.text() == "MICROPHONE IS MUTED"

    def test_long_text_is_cut_at_60_characters(self, osd):
        osd.setStateError("a" * 70)
        assert len(osd.text_label.text()) == 60

    def test_stays_up_while_the_message_is_shown(self, osd):
        osd.setStateError("err")
        osd.hide_osd()                      # e.g. the recording ended meanwhile
        assert osd.fade_anim.endValue() != 0


class TestShowAndHide:
    def test_show_fades_in(self, osd):
        osd.show_osd()
        assert osd.isVisible()
        assert osd.fade_anim.endValue() == 1

    def test_showing_again_while_visible_does_not_restart_the_fade(self, osd):
        osd.show_osd()
        osd.setWindowOpacity(1.0)
        with patch.object(osd.fade_anim, "start") as start:
            osd.show_osd()
        start.assert_not_called()

    def test_hide_fades_out(self, osd):
        osd.show_osd()
        osd.setWindowOpacity(1.0)
        osd.hide_osd()
        assert osd.fade_anim.endValue() == 0

    def test_the_wave_stops_once_the_pill_is_hidden(self, osd):
        osd.setStateRecording()
        osd.hide_osd()
        osd.fade_anim.finished.emit()
        assert not osd.isVisible()
        assert not osd.wave_timer.isActive()

    def test_a_finished_fade_in_keeps_the_pill(self, osd):
        osd.setStateRecording()
        osd.fade_anim.finished.emit()
        assert osd.isVisible()
        assert osd.wave_timer.isActive()

    def test_closing_stops_every_timer(self, osd):
        osd.setStateRecording()
        osd.close()
        assert not osd.wave_timer.isActive()


class TestLanguageAndPosition:
    def test_a_message_follows_the_language(self, osd):
        from core.i18n import set_language
        osd.setStateError("osd.mic_muted")
        english = osd.text_label.text()
        set_language("tr")
        osd.refresh_language()
        assert osd.text_label.text() != english and osd.text_label.text().isupper()

    def test_sits_at_the_top_centre_of_the_screen(self, qapp):
        """Not at the bottom: that is where text is typed in most windows."""
        from PySide6.QtWidgets import QApplication
        pill = MinimalOSD()
        screen = QApplication.primaryScreen().availableGeometry()
        pill.position_osd()
        assert pill.x() == screen.x() + (screen.width() - pill.width()) // 2
        assert pill.y() == screen.y() + 12
        pill.deleteLater()
