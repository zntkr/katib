import sys
import os
from unittest.mock import patch, MagicMock
import pytest

from core.startup import _exe_command, set_startup_enabled, get_startup_enabled
import winreg

class TestExeCommand:
    """Windows başlangıcında çalıştırılacak komut satırı argümanlarının testleri."""
    
    def test_frozen_app(self):
        """PyInstaller ile derlenmiş (exe) uygulamanın yol formatı doğrulanır."""
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", "C:\\mock\\path\\Katib.exe"):
            assert _exe_command() == '"C:\\mock\\path\\Katib.exe"'

    def test_script_app(self):
        """Python ile çalıştırılan geliştirme (script) ortamının yol formatı doğrulanır."""
        with patch.object(sys, "frozen", False, create=True), \
             patch.object(sys, "executable", "C:\\python\\python.exe"), \
             patch.object(sys, "argv", ["C:\\mock\\path\\main.py"]):
            with patch("os.path.abspath", return_value="C:\\mock\\path\\main.py"):
                assert _exe_command() == '"C:\\python\\python.exe" "C:\\mock\\path\\main.py"'


class TestSetStartupEnabled:
    """Windows Kayıt Defteri'ne (Registry) yazma/silme testleri."""

    @patch("core.startup._exe_command", return_value='"mock_cmd"')
    @patch("winreg.OpenKey")
    @patch("winreg.SetValueEx")
    @patch("winreg.CloseKey")
    def test_enable_startup(self, mock_close, mock_set, mock_open, mock_exe):
        """Başlangıca ekleme durumunda SetValueEx çağrısı doğrulanır."""
        mock_key = MagicMock()
        mock_open.return_value = mock_key

        set_startup_enabled(True)

        mock_open.assert_called_once_with(
            winreg.HKEY_CURRENT_USER, 
            r"Software\Microsoft\Windows\CurrentVersion\Run", 
            0, 
            winreg.KEY_SET_VALUE
        )
        mock_set.assert_called_once_with(
            mock_key, "Katib", 0, winreg.REG_SZ, '"mock_cmd"'
        )
        mock_close.assert_called_once_with(mock_key)

    @patch("winreg.OpenKey")
    @patch("winreg.DeleteValue")
    @patch("winreg.CloseKey")
    def test_disable_startup_success(self, mock_close, mock_del, mock_open):
        """Başlangıçtan kaldırma durumunda DeleteValue çağrısı doğrulanır."""
        mock_key = MagicMock()
        mock_open.return_value = mock_key

        set_startup_enabled(False)

        mock_del.assert_called_once_with(mock_key, "Katib")
        mock_close.assert_called_once_with(mock_key)

    @patch("winreg.OpenKey")
    @patch("winreg.DeleteValue")
    @patch("winreg.CloseKey")
    def test_disable_startup_ignores_file_not_found(self, mock_close, mock_del, mock_open):
        """Eğer silinmek istenen key zaten yoksa (FileNotFoundError), uygulamanın çökmediği doğrulanır."""
        mock_key = MagicMock()
        mock_open.return_value = mock_key
        mock_del.side_effect = FileNotFoundError("Anahtar bulunamadı")

        # Herhangi bir hata (Exception) fırlatmadan sessizce geçmeli
        set_startup_enabled(False)

        mock_del.assert_called_once_with(mock_key, "Katib")
        mock_close.assert_called_once_with(mock_key)


class TestGetStartupEnabled:
    """Windows Kayıt Defteri'nden okuma (Sorgulama) testleri."""

    @patch("winreg.OpenKey")
    @patch("winreg.QueryValueEx")
    @patch("winreg.CloseKey")
    def test_returns_true_if_exists(self, mock_close, mock_query, mock_open):
        """Kayıt defterinde Katib anahtarı varsa True döndürdüğü doğrulanır."""
        mock_key = MagicMock()
        mock_open.return_value = mock_key
        
        assert get_startup_enabled() is True

        mock_open.assert_called_once_with(
            winreg.HKEY_CURRENT_USER, 
            r"Software\Microsoft\Windows\CurrentVersion\Run", 
            0, 
            winreg.KEY_READ
        )
        mock_query.assert_called_once_with(mock_key, "Katib")
        mock_close.assert_called_once_with(mock_key)

    @patch("winreg.OpenKey")
    @patch("winreg.QueryValueEx")
    @patch("winreg.CloseKey")
    def test_returns_false_if_not_found(self, mock_close, mock_query, mock_open):
        """Kayıt defterinde anahtar yoksa False döndürdüğü doğrulanır."""
        mock_key = MagicMock()
        mock_open.return_value = mock_key
        mock_query.side_effect = FileNotFoundError()

        assert get_startup_enabled() is False
        mock_close.assert_called_once_with(mock_key)

    @patch("winreg.OpenKey")
    def test_returns_false_on_os_error(self, mock_open):
        """Antivirüs vb. sebeplerle okuma izni verilmezse çökmeyip False döndürdüğü doğrulanır."""
        mock_open.side_effect = OSError("Erişim Engellendi (Access Denied)")

        assert get_startup_enabled() is False