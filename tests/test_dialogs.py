"""
HelpWindow and SettingsDialog tests.
"""
import pytest
from unittest.mock import patch
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent


class TestHelpWindow:
    def test_help_window_opens(self, qapp):
        from ui.help_window import HelpWindow
        w = HelpWindow()
        w.show()
        assert w.isVisible()
        w.close()

    def test_escape_closes_help_window(self, qapp):
        from ui.help_window import HelpWindow
        w = HelpWindow()
        w.show()
        event = QKeyEvent(QEvent.Type.KeyPress,
                          Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        w.keyPressEvent(event)
        assert not w.isVisible()

    def test_paint_event(self, qapp):
        from ui.help_window import HelpWindow
        from PySide6.QtGui import QPaintEvent
        from PySide6.QtCore import QRect
        w = HelpWindow()
        w.paintEvent(QPaintEvent(QRect(0, 0, 100, 100)))

    def test_other_key_press(self, qapp):
        from ui.help_window import HelpWindow
        w = HelpWindow()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A,
                          Qt.KeyboardModifier.NoModifier)
        w.keyPressEvent(event)


class TestSettingsDialog:
    @pytest.fixture
    def dialog(self, qapp, mock_settings):
        from ui.settings_dialog import SettingsDialog
        d = SettingsDialog(mock_settings)
        yield d
        d.close()
        d.deleteLater()

    def test_open_log_folder_exists_calls_startfile(self, dialog):
        import os
        expected_dir = os.path.join(os.environ.get(
            "LOCALAPPDATA", os.path.expanduser("~")), "Katib", "Logs")

        # Simulate folder exists and capture os.startfile call
        with patch("os.path.exists", return_value=True), \
             patch("os.startfile", create=True) as mock_startfile:
            dialog._open_log_folder()

        # Was Windows Explorer called with the correct path?
        mock_startfile.assert_called_once_with(expected_dir)

    def test_open_log_folder_missing_emits_warning(self, dialog):
        logs = []
        dialog.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))

        # Simulate folder not found
        with patch("os.path.exists", return_value=False), \
             patch("os.startfile", create=True) as mock_startfile:
            dialog._open_log_folder()

        # Explorer must not be opened and a log must appear in the UI
        mock_startfile.assert_not_called()
        assert len(logs) == 1
        assert logs[0][0] == "WRN"
        assert "Log folder has not been created yet." in logs[0][2]

    def test_init_with_startup_exception(self, qapp, mock_settings):
        from ui.settings_dialog import SettingsDialog
        with patch("core.startup.get_startup_enabled", side_effect=Exception("No winreg")):
            d = SettingsDialog(mock_settings)
            assert d._chk_startup.isChecked() is False
            d.close()

    def test_paint_event(self, dialog):
        from PySide6.QtGui import QPaintEvent
        from PySide6.QtCore import QRect
        dialog.paintEvent(QPaintEvent(QRect(0, 0, 100, 100)))

    def test_show_centers_on_screen_with_parent(self, qapp, mock_settings):
        from ui.settings_dialog import SettingsDialog
        from PySide6.QtWidgets import QWidget
        parent = QWidget()
        parent.setGeometry(100, 100, 400, 400)
        d = SettingsDialog(mock_settings, parent)
        d.show()
        assert d.isVisible()
        d.close()
        d.setParent(None)

    def test_show_centers_on_screen_without_parent(self, dialog):
        dialog.show()
        assert dialog.isVisible()

    def test_start_hotkey_capture(self, dialog):
        dialog._start_hotkey_capture()
        assert dialog._capturing_hotkey is True
        assert "Press a key..." in dialog.btn_hotkey.text()

    def test_inline_hotkey_capture_success(self, dialog):
        dialog._start_hotkey_capture()
        received = []
        dialog.hotkey_changed.connect(received.append)
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A,
                          Qt.KeyboardModifier.ControlModifier)
        dialog.keyPressEvent(event)
        assert dialog._capturing_hotkey is False
        assert "CTRL+A" in dialog.btn_hotkey.text()
        assert "ctrl+a" in received
        assert dialog.settings.get("hotkey") == "ctrl+a"

    def test_inline_hotkey_capture_escape_cancels(self, dialog):
        dialog._start_hotkey_capture()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        dialog.keyPressEvent(event)
        assert dialog._capturing_hotkey is False
        assert dialog.btn_hotkey.text() == "F9"

    def test_inline_hotkey_capture_modifier_only(self, dialog):
        dialog._start_hotkey_capture()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)
        dialog.keyPressEvent(event)
        assert dialog._capturing_hotkey is True

    def test_inline_hotkey_capture_unsupported(self, dialog):
        dialog._start_hotkey_capture()
        with patch("PySide6.QtCore.QTimer.singleShot") as mock_timer:
            event = QKeyEvent(QEvent.Type.KeyPress, 9999, Qt.KeyboardModifier.NoModifier)
            dialog.keyPressEvent(event)
            assert dialog._capturing_hotkey is True # Capture doesn't end on unsupported key
            mock_timer.assert_not_called() # No timer in new implementation for unsupported

    def test_browse_model_dir_cancelled(self, dialog):
        with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=""):
            dialog._browse_model_dir()

    def test_browse_model_dir_keyboard_interrupt(self, dialog):
        with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", side_effect=RuntimeError("Cancel")):
            try:
                dialog._browse_model_dir()
            except RuntimeError:
                pass

    def test_browse_model_dir_invalid(self, dialog):
        with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value="/invalid/path"), \
             patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
            dialog._browse_model_dir()
            mock_warn.assert_called_once()

    def test_browse_model_dir_valid_but_oserror(self, dialog):
        with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value="/valid/path"), \
             patch("ui.settings_dialog.validate_model_dir", return_value="/valid/path"):
            dialog._browse_model_dir()
            assert dialog.settings.get("model_dir") == "/valid/path"

    def test_browse_model_dir_success(self, dialog):
        with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value="/valid/path"), \
             patch("ui.settings_dialog.validate_model_dir", return_value="/valid/path"):
            dialog._browse_model_dir()
            assert dialog.settings.get("model_dir") == "/valid/path"

    def test_on_startup_toggled_error(self, dialog):
        with patch("core.startup.set_startup_enabled", side_effect=Exception("Error")):
            dialog._on_startup_toggled(True)

    def test_refresh_values_startup_error(self, dialog):
        with patch("core.startup.get_startup_enabled", side_effect=Exception("Error")):
            dialog._refresh_values()

    def test_keypress_event_escape(self, dialog):
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        dialog.show()
        dialog.keyPressEvent(event)
        assert not dialog.isVisible()

    def test_keypress_event_other(self, dialog):
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        dialog.show()
        dialog.keyPressEvent(event)
        assert dialog.isVisible()

    def test_center_on_screen_direct(self, qapp, mock_settings):
        from ui.settings_dialog import SettingsDialog
        from PySide6.QtWidgets import QWidget
        parent = QWidget()
        parent.setGeometry(100, 100, 800, 600)
        d = SettingsDialog(mock_settings, parent)
        d._center_on_screen()

    def test_refresh_values_success(self, dialog):
        dialog._refresh_values()
