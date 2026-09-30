from core.log import get_logger, OK

_log_stt = get_logger("STT")
_log_sys = get_logger("SYS")


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

    try:
        clipboard = QGuiApplication.clipboard()
        current_mime_data = clipboard.mimeData()

        old_mime_data = None
        if current_mime_data:
            old_mime_data = QMimeData()
            for fmt in current_mime_data.formats():
                old_mime_data.setData(fmt, current_mime_data.data(fmt))

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

        if old_mime_data:
            def _restore():
                try:
                    clipboard.setMimeData(old_mime_data)
                except Exception as e:
                    _log_sys.warning(f"Clipboard restore failed: {e}")
            QTimer.singleShot(150, _restore)

        _log_stt.log(OK, "Written (Clipboard)", extra={"transcript": text.strip()})

    except Exception as e:
        _log_sys.error(f"Clipboard operation failed: {e}")
