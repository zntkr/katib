"""Optional GPU (CUDA) acceleration for the Whisper model (ADR-0010).

The GPU is an optimisation, never a requirement: this module only answers "can it be
used?", and the caller falls back to the CPU whenever the answer is no.
"""
import os
import site
import sys
from pathlib import Path

# CTranslate2 loads these by name the first time a CUDA model runs. Measured with
# CTranslate2 4.7.1: a full transcription loads nothing else from the CUDA toolkit.
REQUIRED_DLLS = ("cublas64_12.dll", "cublasLt64_12.dll")

_exposed: set[str] = set()


def candidate_dirs() -> list[Path]:
    """Folders that may hold the CUDA libraries: the frozen bundle or the nvidia-* pip
    wheels (both keep them under nvidia/<package>/bin), then PATH (a CUDA Toolkit install)."""
    if getattr(sys, "frozen", False):
        roots = [Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))]
    else:
        roots = [Path(p) for p in (*site.getsitepackages(), site.getusersitepackages())]
    dirs = [d for root in roots for d in sorted(root.glob("nvidia/*/bin"))]
    dirs += [Path(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    return dirs


def library_dir(dirs: list[Path]) -> Path | None:
    """The first folder that holds every required library; a partial install does not count."""
    for d in dirs:
        if all((d / name).is_file() for name in REQUIRED_DLLS):
            return d
    return None


def unavailable_reason() -> str | None:
    """None when a CUDA model can be loaded; otherwise why not, worded for the log."""
    try:
        if _cuda_device_count() < 1:
            return "no NVIDIA GPU detected"
    except Exception as e:
        return f"GPU query failed: {e}"
    directory = library_dir(candidate_dirs())
    if directory is None:
        return f"CUDA libraries not found ({', '.join(REQUIRED_DLLS)})"
    _expose(directory)
    return None


def compute_type() -> str:
    """float16 is the fastest on cards that support it; older cards only do float32."""
    return "float16" if "float16" in _supported_compute_types() else "float32"


def _expose(directory: Path) -> None:
    """Puts the folder on the DLL search path. Both ways are needed: add_dll_directory is
    ignored by plain LoadLibrary calls, PATH is ignored by the restricted search modes."""
    path = str(directory)
    if path not in _exposed:
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(path)
        _exposed.add(path)
    current = os.environ.get("PATH", "")
    if path not in current.split(os.pathsep):
        os.environ["PATH"] = path + os.pathsep + current


def _cuda_device_count() -> int:
    import ctranslate2
    return ctranslate2.get_cuda_device_count()


def _supported_compute_types() -> set[str]:
    import ctranslate2
    return set(ctranslate2.get_supported_compute_types("cuda"))
