def inject_text(text: str, log_callback=None) -> None:
    """Metni aktif pencereye pano aracılığıyla enjekte eder.

    Mevcut pano içeriğini (resim, dosya vb.) yedekler, metni yapıştırır,
    ardından asenkron olarak eski panoyu geri yükler.
    """
    import keyboard
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
        new_mime_data.setText(text + " ")  # imleci bir sonraki kelimeden ayır
        clipboard.setMimeData(new_mime_data)

        QCoreApplication.processEvents()

        keyboard.send("ctrl+v")

        if old_mime_data:
            def _restore():
                try:
                    clipboard.setMimeData(old_mime_data)
                except Exception as e:
                    if log_callback:
                        log_callback("WRN", "SYS", f"Pano geri yüklenemedi: {e}")
            QTimer.singleShot(150, _restore)

        if log_callback:
            log_callback("OK", "STT", f'Yazıldı: "{text.strip()}"')

    except Exception as e:
        if log_callback:
            log_callback("ERR", "SYS", f"Pano işlemi başarısız: {e}")
