import os
import sys

_mei = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))

_dll_dirs = [
    _mei,
    os.path.join(_mei, 'numpy.libs'),
    os.path.join(_mei, 'ctranslate2'),
    os.path.join(_mei, 'av.libs'),
    os.path.join(_mei, 'PySide6'),
    os.path.join(_mei, '_sounddevice_data', 'portaudio-binaries'),
]

for _d in _dll_dirs:
    if os.path.isdir(_d):
        try:
            os.add_dll_directory(_d)
        except Exception:
            pass
