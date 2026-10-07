# -*- mode: python ; coding: utf-8 -*-
import os
import pathlib
import sys
from PyInstaller.utils.hooks import collect_all

# GPU paketi (plan 0009 Faz 2): `build.bat gpu` KATIB_GPU=1 verir. Program aynıdır; pakete
# yalnız NVIDIA cuBLAS eklenir, böylece NVIDIA kartlı makinede CUDA kurmadan GPU'da çalışır.
_GPU = os.environ.get('KATIB_GPU') == '1'

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
tmp_ret = collect_all('onnxruntime')
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

# --- CUDA/NVIDIA DLL'leri kökten engellenir; GPU paketinde yalnız cuBLAS (aşağıda) geri eklenir ---
_gpu_keywords = [
    'cublas', 'cudnn', 'curand', 'cusparse', 'nvrtc', 'cudart',
    'cufft', 'cufile', 'cusolve', 'cusolver', 'nccl', 'nvjpeg',
    'nvidia_', 'nvinfer', 'nvonnx', 'nvpars',
]

# --- ICU pakete girmez: Qt, Windows'un kendi ICU'sunu kullanır (System32\icuuc.dll, Windows 10 1703+).
# Derleyen bilgisayardaki başka bir ICU (Poppler, Conda…) pakete girerse Qt açılışta
# "Belirtilen yordam bulunamadı" ile düşer: o kopyalar fonksiyonları sürüm ekiyle verir
# (ucnv_open yerine ucnv_open_78) ve paketin kök klasörü DLL aramasında System32'den önce gelir.
# build.bat PATH'i temizleyerek sızıntıyı kaynağında keser; bu, ikinci güvence (plan 0015).
def _is_icu(path):
    name = pathlib.PurePath(str(path).replace('\\', '/')).name.lower()
    return name.startswith('icu') and name.endswith('.dll')

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
    if _is_icu(b_dest) or _is_icu(b_src):
        continue
    filtered_binaries.append((b_dest, b_src))
binaries = filtered_binaries

# --- GPU paketi: core/gpu.py'nin istediği cuBLAS DLL'leri, onun aradığı yere (nvidia/<paket>/bin) ---
# Hangi DLL'lerin gerektiğini ve nerede bulunduğunu core/gpu.py söyler; liste iki yerde tutulmaz.
# cuDNN ve diğer CUDA kitaplıkları gerekmez (ADR-0010: ölçüldü), engelli kalır.
_gpu_keep = set()
if _GPU:
    sys.path.insert(0, SPECPATH)
    from core import gpu as _gpu
    _cuda_dir = _gpu.library_dir(_gpu.candidate_dirs())
    if _cuda_dir is None:
        raise SystemExit("GPU paketi: cuBLAS bulunamadi. requirements-gpu.txt kurulu mu? (build.bat gpu kurar)")
    _dest = 'nvidia/' + _cuda_dir.parent.name + '/bin'
    for _dll in _gpu.REQUIRED_DLLS:
        binaries.append((str(_cuda_dir / _dll), _dest))
        _gpu_keep.add((_dest + '/' + _dll).lower())

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

        # huggingface_hub'ın isteğe bağlı indirme hızlandırıcısı; model indirme onsuz da çalışır.
        # onnxruntime kasıtlı olarak dahil: faster_whisper VAD filtresi için gerekli.
        'hf_xet',

        # Kullanılmayan Python Stdlib Modülleri
        'tkinter', 'unittest', 'doctest', 'pydoc',
        'xmlrpc', 'xmlrpc.client', 'xmlrpc.server',
        'curses', 'antigravity', 'this',
        'idlelib', 'turtledemo', 'turtle',
        'ensurepip', 'venv',

        # Derleme projenin .venv'inden yapılır (ADR-0011): ortamda yalnız constraints.txt'teki
        # paketler vardır. İlgisiz üçüncü parti paketleri (torch, pandas, fastapi…) burada tek
        # tek dışlamak gerekmez; öyle bir liste gerekiyorsa derleme yanlış ortamdan yapılıyordur.
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
    if n in _gpu_keep:
        return False
    return any(k in n for k in _post_exclude) or _is_icu(name)

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