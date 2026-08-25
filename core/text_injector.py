def inject_text(text: str, log_callback=None, injection_method: str = "clipboard") -> None:
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
                
            if log_callback:
                log_callback("OK", "STT", f'Written (Keystroke): "{text.strip()}"')
        except Exception as e:
            if log_callback:
                log_callback("ERR", "SYS", f"Keystroke operation failed: {e}")
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
                    if log_callback:
                        log_callback("WRN", "SYS", f"Clipboard restore failed: {e}")
            QTimer.singleShot(150, _restore)

        if log_callback:
            log_callback("OK", "STT", f'Written (Clipboard): "{text.strip()}"')

    except Exception as e:
        if log_callback:
            log_callback("ERR", "SYS", f"Clipboard operation failed: {e}")
