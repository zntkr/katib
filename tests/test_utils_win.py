from unittest.mock import patch
from ui.utils_win import apply_dark_mode_to_window

class TestUtilsWin:
    def test_apply_dark_mode_to_window_success(self):
        """Tests that the API call is made successfully."""
        with patch("ui.utils_win.ctypes.windll") as mock_windll:
            apply_dark_mode_to_window(123456)
            mock_windll.dwmapi.DwmSetWindowAttribute.assert_called_once()

    def test_apply_dark_mode_to_window_exception(self):
        """Tests that the app does not crash when the API is unavailable on older Windows versions (or Linux/Wine)."""
        with patch("ui.utils_win.ctypes.windll") as mock_windll:
            mock_windll.dwmapi.DwmSetWindowAttribute.side_effect = Exception("DWM API not supported")
            # Exception must be silently swallowed (pass), no crash must occur
            apply_dark_mode_to_window(123456)
