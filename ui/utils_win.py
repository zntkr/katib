import ctypes
from ctypes import wintypes

def apply_dark_mode_to_window(hwnd: int) -> None:
    """
    Windows 10/11 Immersive Dark Mode API'sini zorlar.
    Bu, pencere oluşturulurken oluşan beyaz flash'ı (başlık çubuğu dahil) engeller.
    """
    try:
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 11) veya 19 (Windows 10 1809+)
        # Çoğu modern sistem için 20 standarddır.
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 
            DWMWA_USE_IMMERSIVE_DARK_MODE, 
            ctypes.byref(value), 
            ctypes.sizeof(value)
        )
    except Exception:
        # Eski Windows sürümlerinde (Win7 vb.) hata vermemesi için sessiz geç
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
