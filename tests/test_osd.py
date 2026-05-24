"""
Comprehensive tests for ui/osd.py.
"""
import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt


@pytest.fixture
def osd(qapp):
    from ui.osd import MinimalOSD
    widget = MinimalOSD()
    yield widget
    widget.close()
    widget.deleteLater()


class TestMinimalOSDInit:

    def test_widget_is_created(self, osd):
        assert osd is not None

class TestBuildUI:

    def test_icon_label_exists(self, osd):
        assert hasattr(osd, "icon_label")
        assert osd.icon_label is not None

    def test_text_label_exists(self, osd):
        assert hasattr(osd, "text_label")
        assert osd.text_label is not None

    def test_container_exists(self, osd):
        assert hasattr(osd, "container")
        assert osd.container is not None


class TestSetupAnimations:

    def test_fade_anim_created(self, osd):
        assert hasattr(osd, "fade_anim")
        assert osd.fade_anim is not None

    def test_pulse_timer_created(self, osd):
        assert hasattr(osd, "pulse_timer")
        assert osd.pulse_timer is not None


class TestPulseEffect:

    def test_pulse_val_changes(self, osd):
        before = osd._pulse_val
        osd._pulse_effect()
        assert osd._pulse_val != before

    def test_pulse_dir_reverses_at_lower_boundary(self, osd):
        osd._pulse_val = 0.3
        osd._pulse_dir = -0.06
        osd._pulse_effect()
        assert osd._pulse_dir > 0

    def test_pulse_dir_reverses_at_upper_boundary(self, osd):
        osd._pulse_val = 1.0
        osd._pulse_dir = 0.06
        osd._pulse_effect()
        assert osd._pulse_dir < 0


class TestUpdateColors:

    def test_update_colors_applies_stylesheet(self, osd):
        osd._update_colors()
        ss = osd.container.styleSheet()
        assert "OSDContainer" in ss

    def test_update_colors_with_text_label(self, osd):
        osd._update_colors()
        assert osd.text_label.styleSheet() != ""

class TestSetStateRecording:

    def test_icon_has_pixmap(self, osd):
        with patch.object(osd, "show_osd"):
            osd.setStateRecording()
        assert not osd.icon_label.pixmap().isNull()

    def test_pulse_timer_started(self, osd):
        with patch.object(osd, "show_osd"):
            osd.setStateRecording()
        assert osd.pulse_timer.isActive()
        osd.pulse_timer.stop()


class TestSetStateProcessing:

    def test_icon_has_pixmap(self, osd):
        with patch.object(osd, "show_osd"):
            osd.setStateProcessing()
        assert not osd.icon_label.pixmap().isNull()

    def test_pulse_timer_stopped(self, osd):
        with patch.object(osd, "show_osd"):
            osd.setStateRecording()  # start timer first
            osd.setStateProcessing()
        assert not osd.pulse_timer.isActive()


class TestSetStateError:

    def test_text_is_uppercased(self, osd):
        with patch.object(osd, "show_osd"):
            osd.setStateError("test error")
        assert osd.text_label.text() == "TEST ERROR"

    def test_pulse_timer_stopped(self, osd):
        with patch.object(osd, "show_osd"):
            osd.setStateRecording()
            osd.setStateError("err")
        assert not osd.pulse_timer.isActive()

    def test_icon_has_pixmap(self, osd):
        with patch.object(osd, "show_osd"):
            osd.setStateError("err")
        assert not osd.icon_label.pixmap().isNull()

    def test_long_message_truncated_at_60_chars(self, osd):
        msg = "a" * 70
        with patch.object(osd, "show_osd"):
            osd.setStateError(msg)
        assert len(osd.text_label.text()) == 60

    def test_message_within_60_chars_not_truncated(self, osd):
        msg = "microphone connection lost, please check the connection"
        with patch.object(osd, "show_osd"):
            osd.setStateError(msg)
        assert osd.text_label.text() == msg.upper()


class TestShowOsd:

    def test_sets_window_opacity_to_zero_then_shows(self, osd, qapp):
        with patch.object(osd, "position_osd"):
            osd.show_osd()
        # After show_osd the animation runs toward 1; window must be visible
        assert osd.isVisible()
        osd.hide()

    def test_early_return_when_visible_and_opaque(self, osd, qapp):
        with patch.object(osd, "position_osd"):
            osd.show_osd()
        osd.setWindowOpacity(1.0)
        # Calling again while visible + opacity>0.9 should return early
        start_count_before = osd.fade_anim.state()
        with patch.object(osd.fade_anim, "start") as mock_start:
            osd.show_osd()
        mock_start.assert_not_called()
        osd.hide()


class TestHideOsd:

    def test_animation_starts_toward_zero(self, osd, qapp):
        with patch.object(osd, "position_osd"):
            osd.show_osd()
        osd.setWindowOpacity(1.0)
        osd.hide_osd()
        assert osd.fade_anim.endValue() == 0


class TestOnHideFinished:

    def test_hide_called_when_end_value_is_zero(self, osd, qapp):
        with patch.object(osd, "position_osd"):
            osd.show_osd()
        osd.fade_anim.setEndValue(0)
        with patch.object(osd, "hide") as mock_hide:
            osd._on_hide_finished()
        mock_hide.assert_called_once()

    def test_hide_not_called_when_end_value_is_one(self, osd, qapp):
        with patch.object(osd, "position_osd"):
            osd.show_osd()
        osd.fade_anim.setEndValue(1)
        with patch.object(osd, "hide") as mock_hide:
            osd._on_hide_finished()
        mock_hide.assert_not_called()


class TestPositionOsd:

    def test_move_is_called(self, osd, qapp):
        with patch.object(osd, "move") as mock_move:
            osd.position_osd()
        mock_move.assert_called_once()

    def test_position_is_screen_relative(self, osd, qapp):
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        osd.position_osd()
        geo = osd.geometry()
        assert geo.x() == (screen.width() - osd.width()) // 2
        assert geo.y() == screen.height() - osd.height() - 48
