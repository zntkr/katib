"""
get_settings_path() path çözücü için testler.
Qt veya donanım gerektirmez.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch
from core import settings
from ui.utils import qt_key_to_keyboard, _make_icon

class TestSettingsPath:
    def test_returns_path_object(self):
        assert isinstance(settings.get_settings_path(), Path)

    def test_is_absolute(self):
        assert settings.get_settings_path().is_absolute()

    def test_ends_with_settings_json(self):
        assert settings.get_settings_path().name == "settings.json"

    def test_points_to_home_dir(self):
        expected = Path.home() / ".katib_app" / "settings.json"
        assert settings.get_settings_path() == expected


class TestQtKeyToKeyboard:
    def test_f1_key(self, qapp):
        from PySide6.QtCore import Qt
        assert qt_key_to_keyboard(Qt.Key.Key_F1.value) == "f1"

    def test_f12_key(self, qapp):
        from PySide6.QtCore import Qt
        assert qt_key_to_keyboard(Qt.Key.Key_F12.value) == "f12"

    def test_space_key(self, qapp):
        from PySide6.QtCore import Qt
        assert qt_key_to_keyboard(Qt.Key.Key_Space.value) == "space"

    def test_escape_key(self, qapp):
        from PySide6.QtCore import Qt
        assert qt_key_to_keyboard(Qt.Key.Key_Escape.value) == "esc"

    def test_printable_ascii(self, qapp):
        assert qt_key_to_keyboard(ord("A")) == "a"

    def test_unknown_key_returns_none(self, qapp):
        assert qt_key_to_keyboard(0xFFFF) is None


class TestMakeIcon:
    def test_returns_qicon(self, qapp):
        from PySide6.QtGui import QIcon
        icon = _make_icon("#FF0000")
        assert isinstance(icon, QIcon)

    def test_icon_not_null(self, qapp):
        icon = _make_icon("#00FF00")
        assert not icon.isNull()
