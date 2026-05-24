from unittest.mock import patch
from ui.utils_win import apply_dark_mode_to_window, get_dwm_visual_bounds

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

    def test_get_dwm_visual_bounds_success(self):
        """Returns RECT values as a tuple when DwmGetWindowAttribute returns res==0."""
        with patch("ui.utils_win.ctypes.windll") as mock_windll, \
             patch("ui.utils_win.wintypes.RECT") as mock_rect_cls, \
             patch("ui.utils_win.ctypes.byref", return_value=None), \
             patch("ui.utils_win.ctypes.sizeof", return_value=16):
            mock_rect = mock_rect_cls.return_value
            mock_rect.left, mock_rect.top, mock_rect.right, mock_rect.bottom = 10, 20, 300, 400
            mock_windll.dwmapi.DwmGetWindowAttribute.return_value = 0
            result = get_dwm_visual_bounds(123456)
            assert result == (10, 20, 300, 400)

    def test_get_dwm_visual_bounds_nonzero(self):
        """Returns None when DwmGetWindowAttribute returns res!=0."""
        with patch("ui.utils_win.ctypes.windll") as mock_windll, \
             patch("ui.utils_win.wintypes.RECT"):
            mock_windll.dwmapi.DwmGetWindowAttribute.return_value = 1
            result = get_dwm_visual_bounds(123456)
            assert result is None

    def test_get_dwm_visual_bounds_exception(self):
        """Returns None and does not crash if the DWM API call raises an exception."""
        with patch("ui.utils_win.ctypes.windll") as mock_windll:
            mock_windll.dwmapi.DwmGetWindowAttribute.side_effect = Exception("DWM unavailable")
            result = get_dwm_visual_bounds(123456)
            assert result is None