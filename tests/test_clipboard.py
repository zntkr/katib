import pytest
import sys
from unittest.mock import patch, MagicMock, call

# Ortamda keyboard modülü eksikse bile testlerin hata vermemesi için sahte modül yarat
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
        """Panoda zaten bir veri varken (resim/dosya) metin yapıştırma testi."""
        mock_clipboard = MagicMock()
        mock_qgui.clipboard.return_value = mock_clipboard
        
        # Panoda halihazırda var olan veri (örn: bir resim)
        mock_existing_mime = MagicMock()
        mock_existing_mime.formats.return_value = ["image/png"]
        mock_existing_mime.data.return_value = b"fake_image_data"
        mock_clipboard.mimeData.return_value = mock_existing_mime
        
        # Yeni oluşturulacak QMimeData objelerini yönet
        # İlk çağrı (yedek), ikinci çağrı (yeni metin)
        mock_backup_mime = MagicMock()
        mock_new_text_mime = MagicMock()
        mock_qmimedata_cls.side_effect = [mock_backup_mime, mock_new_text_mime]
        
        mock_log_callback = MagicMock()
        
        inject_text("Test metni", log_callback=mock_log_callback)

        # Panoya ulaşılmış mı?
        mock_qgui.clipboard.assert_called_once()
        
        # Eski veri yedeklenmiş mi?
        mock_backup_mime.setData.assert_called_once_with("image/png", b"fake_image_data")
        
        # Yeni metin set edilmiş mi?
        mock_new_text_mime.setText.assert_called_once_with("Test metni ")
        mock_clipboard.setMimeData.assert_called_once_with(mock_new_text_mime)
        
        # Event loop işletilmiş mi?
        mock_qcore.processEvents.assert_called_once()
        
        # Yapıştırma komutu gönderilmiş mi?
        mock_keyboard_send.assert_called_once_with("ctrl+v")
        
        # Eski panoyu geri yüklemek için timer kurulmuş mu?
        mock_qtimer.singleShot.assert_called_once()
        
        # --- Kapsam (Coverage) Kalkanı: Satır 31-35 ---
        # Timer'a emanet edilen geri yükleme (restore) callback'ini yakala ve çalıştır
        args, kwargs = mock_qtimer.singleShot.call_args
        restore_callback = args[1]  # QTimer.singleShot(delay_ms, callback)
        restore_callback()
        
        # Geri yükleme çalıştığında, gerçekten ESKİ verinin (yedeklenen kopyasının) panoya set edildiğini doğrula
        mock_clipboard.setMimeData.assert_called_with(mock_backup_mime)

        # Log fonksiyonu başarı mesajı ile çağrılmış mı?
        mock_log_callback.assert_called_once_with("OK", "STT", 'Yazıldı: "Test metni"')

    @patch("PySide6.QtGui.QGuiApplication")
    @patch("PySide6.QtCore.QTimer")
    @patch("PySide6.QtCore.QCoreApplication")
    @patch("keyboard.send")
    @patch("PySide6.QtCore.QMimeData")
    def test_inject_text_empty_clipboard(
        self, mock_qmimedata_cls, mock_keyboard_send, mock_qcore, mock_qtimer, mock_qgui
    ):
        """Pano tamamen boşken metin yapıştırma testi."""
        mock_clipboard = MagicMock()
        mock_qgui.clipboard.return_value = mock_clipboard
        
        # Pano boş
        mock_clipboard.mimeData.return_value = None
        
        mock_new_text_mime = MagicMock()
        mock_qmimedata_cls.return_value = mock_new_text_mime
        mock_log_callback = MagicMock()
        
        inject_text("Sadece metin", log_callback=mock_log_callback)
        
        # Pano geri yükleme işlemi (timer) tetiklenmemeli çünkü pano zaten boştu
        mock_qtimer.singleShot.assert_not_called()
        
        # Metin başarıyla yapıştırılmış ve loglanmış olmalı
        mock_keyboard_send.assert_called_once_with("ctrl+v")
        mock_log_callback.assert_called_once_with("OK", "STT", 'Yazıldı: "Sadece metin"')

    @patch("PySide6.QtGui.QGuiApplication")
    @patch("PySide6.QtCore.QTimer")
    @patch("PySide6.QtCore.QCoreApplication")
    @patch("keyboard.send")
    @patch("PySide6.QtCore.QMimeData")
    def test_inject_text_restore_exception(
        self, mock_qmimedata_cls, mock_keyboard_send, mock_qcore, mock_qtimer, mock_qgui
    ):
        """Panoyu geri yüklerken (restore) bir hata olursa uygulamanın çökmemesi ve WRN log atması testi."""
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
        
        # Geri yükleme anında hata fırlatmasını sağla
        mock_clipboard.setMimeData.side_effect = Exception("Pano Kilitli")
        restore_callback()
        
        # Hata yakalanmalı ve WRN logu atılmalı
        mock_log_callback.assert_called_with("WRN", "SYS", "Pano geri yüklenemedi: Pano Kilitli")

    @patch("PySide6.QtGui.QGuiApplication")
    def test_inject_text_exception_handling(self, mock_qgui):
        """Panoya erişim hatası olduğunda uygulamanın çökmemesi ve log atması testi."""
        # Panoya erişmeye çalışıldığında hata fırlat (örn: Antivirüs engeli)
        mock_qgui.clipboard.side_effect = Exception("Erişim Engellendi")
        
        mock_log_callback = MagicMock()
        
        # Çökmemeli (try-except bloğu çalışmalı)
        inject_text("Metin", log_callback=mock_log_callback)
        
        # Hata logu gönderilmiş mi?
        mock_log_callback.assert_called_once()
        args = mock_log_callback.call_args[0]
        assert args[0] == "ERR"
        assert args[1] == "SYS"
        assert "Erişim Engellendi" in args[2]
