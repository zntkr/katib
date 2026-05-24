# -*- mode: python ; coding: utf-8 -*-
import pathlib
from PyInstaller.utils.hooks import collect_all

datas = [('translations', 'translations')]
binaries = []
hiddenimports = []

# numpy.libs DLL'lerini _internal root'a da ekle — Windows'un klasik LoadLibrary
# yolu alt dizinleri görmez; AddDllDirectory frozen context'te güvenilir değil.
try:
    import numpy as _np
    _np_libs = pathlib.Path(_np.__file__).parent.parent / 'numpy.libs'
    if _np_libs.is_dir():
        for _dll in _np_libs.glob('*.dll'):
            binaries += [(str(_dll), '.')]
except ImportError:
    pass

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

# --- CPU-ONLY MİMARİSİ: GPU (CUDA/NVIDIA) DLL'lerini Kökten Engelleme ---
_gpu_keywords = [
    'cublas', 'cudnn', 'curand', 'cusparse', 'nvrtc', 'cudart',
    'cufft', 'cufile', 'cusolve', 'cusolver', 'nccl', 'nvjpeg',
    'nvidia_', 'nvinfer', 'nvonnx', 'nvpars',
]

# --- Gereksiz Binary'leri Kaldır ---
# opengl32sw: software OpenGL rasterizer — Katib 3D/OpenGL kullanmıyor
# Qt6Quick / Qt6Pdf / Qt6Qml: exclude listesinde ama DLL olarak sızdı
# NOT: libx265 / libSvtAv1Enc av.libs'ten SİLİNMEZ — avcodec'in statik
# bağımlılığı, kaldırılırsa av/_core.pyd yüklenemiyor.
_exclude_binaries = [
    'opengl32sw',
    'qt6quick', 'qt6pdf', 'qt6qml', 'qt6qmlmodels', 'qt6qmlworkerscript',
]

filtered_binaries = []
for b_dest, b_src in binaries:
    name_lower = str(b_src).lower()
    if any(k in name_lower for k in _gpu_keywords):
        continue
    if any(k in name_lower for k in _exclude_binaries):
        continue
    filtered_binaries.append((b_dest, b_src))
binaries = filtered_binaries

# --- datas içinden de GPU DLL'lerini Kaldır (cudnn64 gibi datas üzerinden gelenler) ---
datas = [
    (d_src, d_dest) for d_src, d_dest in datas
    if not any(k in str(d_src).lower() for k in _gpu_keywords)
]

# --- Qt Gereksiz İmage Format Plugin'lerini Kaldır ---
# Katib yalnızca SVG, ICO ve PNG kullanır.
_keep_imgfmt = {'qsvg', 'qico', 'qpng', 'qjpeg'}
filtered_datas = []
for d_src, d_dest in datas:
    src_lower = str(d_src).lower().replace('\\', '/')
    if 'imageformats' in src_lower:
        plugin_name = pathlib.Path(d_src).stem.lower()
        if plugin_name not in _keep_imgfmt:
            continue
    filtered_datas.append((d_src, d_dest))
datas = filtered_datas

# --- Qt .qm Çeviri Dosyalarını Kaldır ---
# Qt'nin kendi UI çevirileri — Katib bunları kullanmıyor.
datas = [
    (d_src, d_dest) for d_src, d_dest in datas
    if not (str(d_src).lower().endswith('.qm') and 'qt' in str(d_src).lower())
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hooks/rthook_dll_paths.py'],
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

        # Kullanılmayan Python Stdlib Modülleri
        'unittest', 'doctest', 'pydoc',
        'xmlrpc', 'xmlrpc.client', 'xmlrpc.server',
        'curses', 'antigravity', 'this',
        'lib2to3', 'idlelib', 'turtledemo', 'turtle',
        'ensurepip', 'venv', 'distutils',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- Analysis sonrası filtreleme ---
_post_exclude = [
    'opengl32sw',
    'qt6quick', 'qt6pdf', 'qt6qml',
    'qt6qmlmodels', 'qt6qmlworkerscript',
] + _gpu_keywords

def _should_exclude(name):
    n = name.lower().replace('\\', '/').replace('-', '_')
    return any(k in n for k in _post_exclude)

a.binaries = TOC([b for b in a.binaries if not _should_exclude(b[0])])
a.datas    = TOC([d for d in a.datas    if not _should_exclude(d[0])])

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