import pytest
import sys
from unittest.mock import patch, MagicMock, call

# Create a fake module so tests do not fail even if the keyboard module is not installed
sys.modules["keyboard"] = MagicMock()

import core.text_injector as text_injector
from core.text_injector import inject_text
from tests.log_helpers import on_log_entry


@pytest.fixture(autouse=True)
def _no_restore_pending():
    """The injector remembers the user's clipboard between pastes; each test starts clean."""
    text_injector._user_clipboard = None
    yield
    text_injector._user_clipboard = None


def _mime(*formats: str) -> MagicMock:
    mime = MagicMock()
    mime.formats.return_value = list(formats)
    return mime


class TestPastesInQuickSuccession:
    """A hands-free dictation on the GPU pastes sentence after sentence. When every paste
    backed up and restored the clipboard on its own, a second paste inside the 150 ms took
    the first sentence for the user's clipboard, and the first restore could land before the
    second sentence was read by the target window."""

    def _two_pastes(self, mock_qmimedata_cls, mock_qtimer, mock_qgui):
        clipboard = MagicMock()
        mock_qgui.clipboard.return_value = clipboard
        clipboard.mimeData.side_effect = [_mime("text/plain"), _mime("text/plain")]  # the user's, then sentence one
        backup, first, second = MagicMock(), MagicMock(), MagicMock()
        mock_qmimedata_cls.side_effect = [backup, first, second, MagicMock()]
        inject_text("Bir")
        inject_text("İki")
        restores = [c.args[1] for c in mock_qtimer.singleShot.call_args_list]
        return clipboard, backup, second, restores

    @patch("PySide6.QtGui.QGuiApplication")
    @patch("PySide6.QtCore.QTimer")
    @patch("PySide6.QtCore.QCoreApplication")
    @patch("keyboard.send")
    @patch("PySide6.QtCore.QMimeData")
    def test_the_users_clipboard_is_backed_up_once(self, mock_qmimedata_cls, _send, _qcore, mock_qtimer, mock_qgui):
        clipboard, backup, _, _ = self._two_pastes(mock_qmimedata_cls, mock_qtimer, mock_qgui)
        assert clipboard.mimeData.call_count == 1   # sentence one is never mistaken for the user's

    @patch("PySide6.QtGui.QGuiApplication")
    @patch("PySide6.QtCore.QTimer")
    @patch("PySide6.QtCore.QCoreApplication")
    @patch("keyboard.send")
    @patch("PySide6.QtCore.QMimeData")
    def test_the_first_restore_leaves_the_second_sentence_alone(self, mock_qmimedata_cls, _send, _qcore, mock_qtimer, mock_qgui):
        clipboard, _, second, restores = self._two_pastes(mock_qmimedata_cls, mock_qtimer, mock_qgui)
        restores[0]()   # 150 ms after sentence one; sentence two may not have been read yet
        assert clipboard.setMimeData.call_args_list[-1] == call(second)

    @patch("PySide6.QtGui.QGuiApplication")
    @patch("PySide6.QtCore.QTimer")
    @patch("PySide6.QtCore.QCoreApplication")
    @patch("keyboard.send")
    @patch("PySide6.QtCore.QMimeData")
    def test_the_last_restore_puts_the_users_clipboard_back(self, mock_qmimedata_cls, _send, _qcore, mock_qtimer, mock_qgui):
        clipboard, backup, _, restores = self._two_pastes(mock_qmimedata_cls, mock_qtimer, mock_qgui)
        for restore in restores:
            restore()
        assert clipboard.setMimeData.call_args_list[-1] == call(backup)

    @patch("PySide6.QtGui.QGuiApplication")
    @patch("PySide6.QtCore.QTimer")
    @patch("PySide6.QtCore.QCoreApplication")
    @patch("keyboard.send")
    @patch("PySide6.QtCore.QMimeData")
    def test_a_paste_after_the_restore_backs_up_again(self, mock_qmimedata_cls, _send, _qcore, mock_qtimer, mock_qgui):
        """Sentences seconds apart: by then the user may have copied something new."""
        clipboard = MagicMock()
        mock_qgui.clipboard.return_value = clipboard
        clipboard.mimeData.side_effect = [_mime("text/plain"), _mime("image/png")]
        inject_text("Bir")
        mock_qtimer.singleShot.call_args.args[1]()
        inject_text("İki")
        assert clipboard.mimeData.call_count == 2


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
        on_log_entry(mock_log_callback)

        inject_text("Test text")

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
        mock_log_callback.assert_called_once_with("OK", "STT", "Written (Clipboard): 'Test text'")

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
        on_log_entry(mock_log_callback)

        inject_text("Text only")

        # Clipboard restore (timer) must not be triggered because the clipboard was already empty
        mock_qtimer.singleShot.assert_not_called()

        # Text must have been pasted and logged successfully
        mock_keyboard_send.assert_called_once_with("ctrl+v")
        mock_log_callback.assert_called_once_with("OK", "STT", "Written (Clipboard): 'Text only'")

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
        on_log_entry(mock_log_callback)
        inject_text("Test")

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
        on_log_entry(mock_log_callback)

        # Must not crash (try-except block must run)
        inject_text("Text")

        # Was an error log sent?
        mock_log_callback.assert_called_once()
        args = mock_log_callback.call_args[0]
        assert args[0] == "ERR"
        assert args[1] == "SYS"
        assert "Access Denied" in args[2]

    @patch("sys.platform", "win32")
    @patch("keyboard.write")
    def test_inject_text_keystroke_win32(self, mock_keyboard_write):
        """Test typing text via keystroke simulation."""
        mock_log_callback = MagicMock()
        on_log_entry(mock_log_callback)
        inject_text("Hello", injection_method="keystroke")
        mock_keyboard_write.assert_called_once_with("Hello ")
        mock_log_callback.assert_called_once_with("OK", "STT", "Written (Keystroke): 'Hello'")
