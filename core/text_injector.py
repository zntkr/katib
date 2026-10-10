from core.log import get_logger, OK

_log_stt = get_logger("STT")
_log_sys = get_logger("SYS")

# A hands-free dictation pastes sentence after sentence. The user's clipboard is backed up
# before the first paste of such a run and put back once, after the last: when every paste did
# both on its own, a second paste inside the delay took the first sentence for the user's
# clipboard, and the first restore could land before the second sentence had been read.
_RESTORE_DELAY_MS = 150
_user_clipboard = None   # the backup (QMimeData) while a restore is pending
_latest_paste = 0        # only the newest paste's timer restores


def inject_text(text: str, injection_method: str = "clipboard") -> None:
    """Injects text into the active window.
    
    If injection_method == 'clipboard', backs up current clipboard contents,
    pastes the text, then restores the old clipboard asynchronously.
    
    If injection_method == 'keystroke', uses virtual keyboard to type the text
    character by character (safer but slower).
    """
    import sys
    
    if injection_method == "keystroke":
        try:
            if sys.platform == "win32":
                import keyboard
                keyboard.write(text + " ")
            else:
                from pynput.keyboard import Controller
                _kb = Controller()
                _kb.type(text + " ")
                
            _log_stt.log(OK, "Written (Keystroke)", extra={"transcript": text.strip()})
        except Exception as e:
            _log_sys.error(f"Keystroke operation failed: {e}")
        return

    # Default to clipboard injection
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtCore import QTimer, QCoreApplication, QMimeData

    global _user_clipboard, _latest_paste
    try:
        clipboard = QGuiApplication.clipboard()
        if _user_clipboard is None:  # else an earlier paste's text is on it, not the user's
            current_mime_data = clipboard.mimeData()
            if current_mime_data:
                backup = QMimeData()
                for fmt in current_mime_data.formats():
                    backup.setData(fmt, current_mime_data.data(fmt))
                _user_clipboard = backup

        new_mime_data = QMimeData()
        new_mime_data.setText(text + " ")  # separate cursor from the next word
        clipboard.setMimeData(new_mime_data)

        QCoreApplication.processEvents()

        if sys.platform == "win32":
            import keyboard
            keyboard.send("ctrl+v")
        else:
            from pynput.keyboard import Controller, Key
            _kb = Controller()
            modifier = Key.cmd if sys.platform == "darwin" else Key.ctrl
            with _kb.pressed(modifier):
                _kb.press("v")
                _kb.release("v")

        if _user_clipboard is not None:
            _latest_paste += 1
            this_paste = _latest_paste

            def _restore():
                global _user_clipboard
                if this_paste != _latest_paste:
                    return  # a later paste may not have been read yet; its timer restores
                backup, _user_clipboard = _user_clipboard, None
                try:
                    clipboard.setMimeData(backup)
                except Exception as e:
                    _log_sys.warning(f"Clipboard restore failed: {e}")
            QTimer.singleShot(_RESTORE_DELAY_MS, _restore)

        _log_stt.log(OK, "Written (Clipboard)", extra={"transcript": text.strip()})

    except Exception as e:
        _log_sys.error(f"Clipboard operation failed: {e}")
