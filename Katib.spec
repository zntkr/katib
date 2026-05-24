# -*- mode: python ; coding: utf-8 -*-
import pathlib
from PyInstaller.utils.hooks import collect_all

datas = [('translations', 'translations')]
binaries = []
hiddenimports = []

# STT kütüphanesinin DLL ve Data dosyalarını güvenlice topluyoruz
tmp_ret = collect_all('ctranslate2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('faster_whisper')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# sounddevice: tek .py dosyası + _sounddevice_data paketi (PortAudio DLL)
# collect_all bunu atlıyor — kurulum dizinini dinamik olarak buluyoruz.
try:
    import sounddevice as _sd
    _sd_site = pathlib.Path(_sd.__file__).parent
    _sd_data_dir = _sd_site / '_sounddevice_data'
    if _sd_data_dir.exists():
        datas += [(str(_sd_data_dir), '_sounddevice_data')]
except ImportError:
    import sys, site
    for _sp in site.getsitepackages() + [site.getusersitepackages()]:
        _sd_data_dir = pathlib.Path(_sp) / '_sounddevice_data'
        if _sd_data_dir.exists():
            datas += [(str(_sd_data_dir), '_sounddevice_data')]
            break
hiddenimports += ['sounddevice', '_sounddevice']

# --- CPU-ONLY MİMARİSİ: GPU (CUDA) DLL'lerini Kökten Engelleme ---
# PyInstaller'ın 1.5 GB'lık gereksiz NVIDIA dosyalarını kopyalamasını baştan yasaklıyoruz.
cuda_keywords = ['cublas', 'cudnn', 'curand', 'cusparse', 'nvrtc', 'cudart']
filtered_binaries = []
for b_dest, b_src in binaries:
    if not any(k in str(b_src).lower() for k in cuda_keywords):
        filtered_binaries.append((b_dest, b_src))
binaries = filtered_binaries

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Kullanılmayan Devasa PySide6 Bileşenleri
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQuickControls2',
        'PySide6.QtQuick3D', 'PySide6.Qt3DCore', 'PySide6.QtPdf',
        'PySide6.QtWebSockets', 'PySide6.QtWebChannel', 'PySide6.QtTest',
        'PySide6.QtSql', 'PySide6.QtXml', 'PySide6.QtNfc', 'PySide6.QtDesigner',
        'PySide6.QtHelp', 'PySide6.QtNetworkAuth', 'PySide6.QtBluetooth',
        'PySide6.QtLocation', 'PySide6.QtPositioning', 'PySide6.QtRemoteObjects',
        'PySide6.QtSensors', 'PySide6.QtSerialPort', 'PySide6.QtTextToSpeech',
        'PySide6.QtMultimediaWidgets',
        # PySide6.QtMultimedia kasıtlı olarak dahil: QMediaDevices (mikrofon listesi) için gerekli
        'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
        'PySide6.QtPrintSupport', 'PySide6.QtConcurrent',
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras', 'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic', 'PySide6.Qt3DRender',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtStateMachine',

        # Gereksiz Olabilecek Standart & 3. Parti Kütüphaneler
        'tkinter', 'matplotlib', 'IPython', 'scipy', 'PIL', 'PyQt5', 'PyQt6',

        # Büyük ve Kullanılmayan Paketler (~490 MB tasarruf)
        'torch', 'torchvision', 'torchaudio',
        'transformers',
        'onnxruntime', 'onnxruntime.capi',
        'pandas', 'pandas.core',
        'sklearn', 'sklearn.utils',
        'grpc', 'grpc._cython',
        'lxml',
        'hf_xet', 'xet_client',

        # Kullanılmayan 3. Parti Paketler
        'cryptography',
        'pydantic', 'pydantic_core', 'pydantic_settings',
        'aiohttp', 'aiohttp_socks', 'aiosignal',
        'fastapi', 'starlette', 'uvicorn',
        'flask', 'werkzeug',
        'anthropic',
        'chromadb',
        'sentence_transformers',
        'sympy', 'networkx', 'paramiko', 'kubernetes', 'neo4j', 'libcst',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Katib',
    icon='katib.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Katib',
)