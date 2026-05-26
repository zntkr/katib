def inject_text(text: str, log_callback=None) -> None:
    """Injects text into the active window via the clipboard.

    Backs up current clipboard contents (image, file, etc.), pastes the text,
    then restores the old clipboard asynchronously.
    """
    import sys
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
            with _kb.pressed(Key.ctrl):
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
            log_callback("OK", "STT", f'Written: "{text.strip()}"')

    except Exception as e:
        if log_callback:
            log_callback("ERR", "SYS", f"Clipboard operation failed: {e}")
