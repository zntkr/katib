"""HelpWindow: the user guide opened from the tray menu or the settings window."""
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt, QEvent, QRect
from PySide6.QtGui import QKeyEvent, QPaintEvent


def _key(key) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


@pytest.fixture
def help_window(qapp, mock_settings):
    from ui.help_window import HelpWindow
    window = HelpWindow(settings=mock_settings)
    yield window
    window.close()


class TestHelpWindow:
    def test_opens(self, help_window):
        help_window.show()
        assert help_window.isVisible()

    def test_opens_without_settings(self, qapp):
        from ui.help_window import HelpWindow
        window = HelpWindow()
        window.show()
        assert window.isVisible()
        window.close()

    def test_escape_closes_it(self, help_window):
        help_window.show()
        help_window.keyPressEvent(_key(Qt.Key.Key_Escape))
        assert not help_window.isVisible()

    def test_other_keys_leave_it_open(self, help_window):
        help_window.show()
        help_window.keyPressEvent(_key(Qt.Key.Key_A))
        assert help_window.isVisible()

    def test_paints_its_background(self, help_window):
        help_window.paintEvent(QPaintEvent(QRect(0, 0, 100, 100)))

    def test_opens_even_when_dark_title_bar_is_unavailable(self, help_window):
        with patch("ui.help_window.apply_dark_mode_to_window", side_effect=Exception("No DWM")):
            help_window.show()
        assert help_window.isVisible()
