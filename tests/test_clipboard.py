import pytest
import sys
from unittest.mock import patch, MagicMock, call

# Create a fake module so tests do not fail even if the keyboard module is not installed
sys.modules["keyboard"] = MagicMock()

from core.text_injector import inject_text

class TestClipboardInjectText:

    @patch("PySide6.QtGui.QGuiApplication")
    @patch("PySide6.QtCore.QTimer")
    @patch("PySide6.QtCore.QCoreApplication")
    @patch("keyboard.send")
    @patch("PySide6.QtCore.QMimeData")
    def test_inject_text_success_with_existing_clipboard(
        self, mock_qmimedata_cls, mock_keyboard_send, mock_qcore, mock_qtimer, mock_qgui
    ):
        """Test pasting text when the clipboard already contains data (image/file)."""
        mock_clipboard = MagicMock()
        mock_qgui.clipboard.return_value = mock_clipboard

        # Data already on the clipboard (e.g. an image)
        mock_existing_mime = MagicMock()
        mock_existing_mime.formats.return_value = ["image/png"]
        mock_existing_mime.data.return_value = b"fake_image_data"
        mock_clipboard.mimeData.return_value = mock_existing_mime

        # Manage the QMimeData objects that will be created
        # First call (backup), second call (new text)
        mock_backup_mime = MagicMock()
        mock_new_text_mime = MagicMock()
        mock_qmimedata_cls.side_effect = [mock_backup_mime, mock_new_text_mime]

        mock_log_callback = MagicMock()

        inject_text("Test text", log_callback=mock_log_callback)

        # Was the clipboard accessed?
        mock_qgui.clipboard.assert_called_once()

        # Was the old data backed up?
        mock_backup_mime.setData.assert_called_once_with("image/png", b"fake_image_data")

        # Was the new text set?
        mock_new_text_mime.setText.assert_called_once_with("Test text ")
        mock_clipboard.setMimeData.assert_called_once_with(mock_new_text_mime)

        # Was the event loop processed?
        mock_qcore.processEvents.assert_called_once()

        # Was the paste command sent?
        mock_keyboard_send.assert_called_once_with("ctrl+v")

        # Was a timer set up to restore the old clipboard?
        mock_qtimer.singleShot.assert_called_once()

        # --- Coverage shield: lines 31-35 ---
        # Capture and run the restore callback passed to the timer
        args, kwargs = mock_qtimer.singleShot.call_args
        restore_callback = args[1]  # QTimer.singleShot(delay_ms, callback)
        restore_callback()

        # Verify that the OLD backed-up data was actually restored to the clipboard
        mock_clipboard.setMimeData.assert_called_with(mock_backup_mime)

        # Was the log callback called with a success message?
        mock_log_callback.assert_called_once_with("OK", "STT", 'Written: "Test text"')

    @patch("PySide6.QtGui.QGuiApplication")
    @patch("PySide6.QtCore.QTimer")
    @patch("PySide6.QtCore.QCoreApplication")
    @patch("keyboard.send")
    @patch("PySide6.QtCore.QMimeData")
    def test_inject_text_empty_clipboard(
        self, mock_qmimedata_cls, mock_keyboard_send, mock_qcore, mock_qtimer, mock_qgui
    ):
        """Test pasting text when the clipboard is completely empty."""
        mock_clipboard = MagicMock()
        mock_qgui.clipboard.return_value = mock_clipboard

        # Clipboard is empty
        mock_clipboard.mimeData.return_value = None

        mock_new_text_mime = MagicMock()
        mock_qmimedata_cls.return_value = mock_new_text_mime
        mock_log_callback = MagicMock()

        inject_text("Text only", log_callback=mock_log_callback)

        # Clipboard restore (timer) must not be triggered because the clipboard was already empty
        mock_qtimer.singleShot.assert_not_called()

        # Text must have been pasted and logged successfully
        mock_keyboard_send.assert_called_once_with("ctrl+v")
        mock_log_callback.assert_called_once_with("OK", "STT", 'Written: "Text only"')

    @patch("PySide6.QtGui.QGuiApplication")
    @patch("PySide6.QtCore.QTimer")
    @patch("PySide6.QtCore.QCoreApplication")
    @patch("keyboard.send")
    @patch("PySide6.QtCore.QMimeData")
    def test_inject_text_restore_exception(
        self, mock_qmimedata_cls, mock_keyboard_send, mock_qcore, mock_qtimer, mock_qgui
    ):
        """Test that the app does not crash and emits a WRN log when a restore error occurs."""
        mock_clipboard = MagicMock()
        mock_qgui.clipboard.return_value = mock_clipboard

        mock_existing_mime = MagicMock()
        mock_existing_mime.formats.return_value = ["text/plain"]
        mock_clipboard.mimeData.return_value = mock_existing_mime

        mock_backup_mime = MagicMock()
        mock_new_text_mime = MagicMock()
        mock_qmimedata_cls.side_effect = [mock_backup_mime, mock_new_text_mime]

        mock_log_callback = MagicMock()
        inject_text("Test", log_callback=mock_log_callback)

        args, kwargs = mock_qtimer.singleShot.call_args
        restore_callback = args[1]

        # Cause an error during the restore
        mock_clipboard.setMimeData.side_effect = Exception("Clipboard Locked")
        restore_callback()

        # Error must be caught and a WRN log emitted
        mock_log_callback.assert_called_with("WRN", "SYS", "Clipboard restore failed: Clipboard Locked")

    @patch("PySide6.QtGui.QGuiApplication")
    def test_inject_text_exception_handling(self, mock_qgui):
        """Test that the app does not crash and emits a log when clipboard access fails."""
        # Raise an error when trying to access the clipboard (e.g. blocked by antivirus)
        mock_qgui.clipboard.side_effect = Exception("Access Denied")

        mock_log_callback = MagicMock()

        # Must not crash (try-except block must run)
        inject_text("Text", log_callback=mock_log_callback)

        # Was an error log sent?
        mock_log_callback.assert_called_once()
        args = mock_log_callback.call_args[0]
        assert args[0] == "ERR"
        assert args[1] == "SYS"
        assert "Access Denied" in args[2]
