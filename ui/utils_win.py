import ctypes
from ctypes import wintypes

def apply_dark_mode_to_window(hwnd: int) -> None:
    """
    Forces the Windows 10/11 Immersive Dark Mode API.
    This prevents the white flash (including the title bar) that occurs when the window is created.
    """
    try:
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 11) or 19 (Windows 10 1809+)
        # 20 is the standard for most modern systems.
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 
            DWMWA_USE_IMMERSIVE_DARK_MODE, 
            ctypes.byref(value), 
            ctypes.sizeof(value)
        )
    except Exception:
        # Silently ignore on older Windows versions (Win7, etc.) that don't support the API.
        pass

def get_dwm_visual_bounds(hwnd: int) -> tuple[int, int, int, int] | None:
    """Returns visual (DWM) bounds: left, top, right, bottom."""
    try:
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        rect = wintypes.RECT()
        res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
        )
        if res == 0:
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        pass
    return None
