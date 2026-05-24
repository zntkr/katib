import sys
import os
from unittest.mock import patch, MagicMock
import pytest

from core.startup import _exe_command, set_startup_enabled, get_startup_enabled
import winreg

class TestExeCommand:
    """Tests for the command-line arguments used when launching the app at Windows startup."""

    def test_frozen_app(self):
        """Verifies the path format for a PyInstaller-compiled (exe) application."""
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", "C:\\mock\\path\\Katib.exe"):
            assert _exe_command() == '"C:\\mock\\path\\Katib.exe"'

    def test_script_app(self):
        """Verifies the path format for the development (script) environment run with Python."""
        with patch.object(sys, "frozen", False, create=True), \
             patch.object(sys, "executable", "C:\\python\\python.exe"), \
             patch.object(sys, "argv", ["C:\\mock\\path\\main.py"]):
            with patch("os.path.abspath", return_value="C:\\mock\\path\\main.py"):
                assert _exe_command() == '"C:\\python\\python.exe" "C:\\mock\\path\\main.py"'


class TestSetStartupEnabled:
    """Tests for writing to and deleting from the Windows Registry."""

    @patch("core.startup._exe_command", return_value='"mock_cmd"')
    @patch("winreg.OpenKey")
    @patch("winreg.SetValueEx")
    @patch("winreg.CloseKey")
    def test_enable_startup(self, mock_close, mock_set, mock_open, mock_exe):
        """Verifies that SetValueEx is called when adding the app to startup."""
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
        """Verifies that DeleteValue is called when removing the app from startup."""
        mock_key = MagicMock()
        mock_open.return_value = mock_key

        set_startup_enabled(False)

        mock_del.assert_called_once_with(mock_key, "Katib")
        mock_close.assert_called_once_with(mock_key)

    @patch("winreg.OpenKey")
    @patch("winreg.DeleteValue")
    @patch("winreg.CloseKey")
    def test_disable_startup_ignores_file_not_found(self, mock_close, mock_del, mock_open):
        """Verifies the app does not crash if the key being deleted does not exist (FileNotFoundError)."""
        mock_key = MagicMock()
        mock_open.return_value = mock_key
        mock_del.side_effect = FileNotFoundError("Key not found")

        # Should pass silently without raising any exception
        set_startup_enabled(False)

        mock_del.assert_called_once_with(mock_key, "Katib")
        mock_close.assert_called_once_with(mock_key)


class TestGetStartupEnabled:
    """Tests for reading (querying) the Windows Registry."""

    @patch("winreg.OpenKey")
    @patch("winreg.QueryValueEx")
    @patch("winreg.CloseKey")
    def test_returns_true_if_exists(self, mock_close, mock_query, mock_open):
        """Verifies that True is returned when the Katib key exists in the registry."""
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
        """Verifies that False is returned when the key is not found in the registry."""
        mock_key = MagicMock()
        mock_open.return_value = mock_key
        mock_query.side_effect = FileNotFoundError()

        assert get_startup_enabled() is False
        mock_close.assert_called_once_with(mock_key)

    @patch("winreg.OpenKey")
    def test_returns_false_on_os_error(self, mock_open):
        """Verifies the app returns False without crashing when read access is denied (e.g. by antivirus)."""
        mock_open.side_effect = OSError("Access Denied")

        assert get_startup_enabled() is False