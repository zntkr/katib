"""Packaging guards (plan 0015): DLLs from tools on the build machine must not reach the bundle.

A Poppler ICU 78 on the build machine's PATH was packed next to Qt; Qt then failed to start
with "the specified procedure could not be found". These read build.bat and Katib.spec; they
do not run PyInstaller (plan 0015 Faz 2 does, by hand)."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = (ROOT / "build.bat").read_text(encoding="utf-8").splitlines()
SPEC = (ROOT / "Katib.spec").read_text(encoding="utf-8")


def _line_index(pattern: str) -> int:
    return next(i for i, line in enumerate(BUILD) if re.search(pattern, line, re.IGNORECASE))


class TestBuildPath:
    def test_pyinstaller_runs_with_only_the_windows_folders_on_path(self):
        pyinstaller = _line_index(r"-m PyInstaller")
        path_sets = [i for i, line in enumerate(BUILD) if re.match(r'\s*set\s+"?PATH=', line, re.IGNORECASE)]
        assert path_sets and path_sets[-1] < pyinstaller, "PATH must be set before PyInstaller runs"
        value = re.match(r'\s*set\s+"?PATH=([^"]*)', BUILD[path_sets[-1]], re.IGNORECASE).group(1)
        assert all(part.upper().startswith("%SYSTEMROOT%") for part in value.split(";")), value

    def test_the_path_change_does_not_outlive_the_script(self):
        assert _line_index(r"^\s*setlocal\b") < _line_index(r'set\s+"?PATH=')


def _is_icu():
    """The spec's own _is_icu(), run as written there."""
    source = re.search(r"^def _is_icu\(path\):\n(?:    .*\n)+", SPEC, re.MULTILINE).group(0)
    namespace = {"pathlib": pathlib}
    exec(source, namespace)
    return namespace["_is_icu"]


class TestSpecKeepsIcuOut:
    def test_icu_dlls_are_recognised_wherever_they_come_from(self):
        is_icu = _is_icu()
        for name in ("icuuc.dll", "icudt78.dll", "ICUIN.DLL", r"C:\tools\poppler\Library\bin\icuuc.dll",
                     "C:/tools/poppler/Library/bin/icudt78.dll"):
            assert is_icu(name), name

    def test_other_files_are_not(self):
        is_icu = _is_icu()
        for name in ("Qt6Core.dll", "unicodedata.pyd", r"PySide6\Qt6Gui.dll", "libicu.dll", "icu.txt",
                     r"C:\icu\Qt6Core.dll"):
            assert not is_icu(name), name

    def test_both_filters_use_it(self):
        assert "if _is_icu(b_dest) or _is_icu(b_src):" in SPEC  # binaries collected by hand
        assert "or _is_icu(name)" in re.search(r"def _should_exclude.*?\n\n", SPEC, re.DOTALL).group(0)  # after Analysis


# ------------------------------------------------------------------ GPU package (plan 0009 Faz 2)

ISS = (ROOT / "Katib.iss").read_text(encoding="utf-8")


def _should_exclude(keep: set[str]):
    """The spec's own _should_exclude(), with the GPU keep-list given."""
    source = re.search(r"^def _should_exclude\(name\):\n(?:    .*\n)+", SPEC, re.MULTILINE).group(0)
    post = re.search(r"^_post_exclude = \[(.*?)\] \+ _gpu_keywords", SPEC, re.MULTILINE | re.DOTALL).group(1)
    keywords = re.search(r"^_gpu_keywords = \[(.*?)\]", SPEC, re.MULTILINE | re.DOTALL).group(1)
    namespace = {"_gpu_keep": keep, "_is_icu": _is_icu(),
                 "_post_exclude": eval("[" + post + "]") + eval("[" + keywords + "]")}
    exec(source, namespace)
    return namespace["_should_exclude"]


class TestGpuPackage:
    KEEP = {"nvidia/cublas/bin/cublas64_12.dll", "nvidia/cublas/bin/cublaslt64_12.dll"}

    def test_the_gpu_package_keeps_cublas_where_core_gpu_looks(self):
        exclude = _should_exclude(self.KEEP)
        assert not exclude(r"nvidia\cublas\bin\cublas64_12.dll")
        assert not exclude(r"nvidia\cublas\bin\cublasLt64_12.dll")

    def test_other_cuda_libraries_stay_out_even_in_the_gpu_package(self):
        exclude = _should_exclude(self.KEEP)
        for name in ("cudnn64_9.dll", "cublas64_12.dll", r"ctranslate2\cudnn_ops64_9.dll", "icuuc.dll"):
            assert exclude(name), name  # a copy outside nvidia\cublas\bin is not the one kept

    def test_the_normal_package_keeps_no_cublas(self):
        exclude = _should_exclude(set())
        assert exclude(r"nvidia\cublas\bin\cublas64_12.dll")

    def test_the_spec_takes_the_dll_list_and_folder_from_core_gpu(self):
        # one list of required DLLs (core/gpu.py::REQUIRED_DLLS), and the folder core/gpu.py searches
        assert "_gpu.REQUIRED_DLLS" in SPEC and "_gpu.library_dir(_gpu.candidate_dirs())" in SPEC
        assert "'nvidia/' + _cuda_dir.parent.name + '/bin'" in SPEC
        assert 'root.glob("nvidia/*/bin")' in (ROOT / "core" / "gpu.py").read_text(encoding="utf-8")

    def test_only_build_bat_gpu_turns_it_on(self):
        text = "\n".join(BUILD)
        assert re.search(r'set "KATIB_GPU="\s*\n', text), "a normal build must not inherit KATIB_GPU"
        assert re.search(r'if /i "%~1"=="gpu" \(\s*\n\s*set "KATIB_GPU=1"', text)
        assert "requirements-gpu.txt" in text and "if defined KATIB_GPU" in text
        assert "%ISCC% %ISCC_GPU% Katib.iss" in text

    def test_the_gpu_installer_has_its_own_name(self):
        assert re.search(r'#ifdef Gpu\s*\n\s*#define Variant "_GPU"', ISS)
        assert "OutputBaseFilename=Katib_Setup_{#AppVersion}{#Variant}" in ISS

    def test_setup_removes_a_leftover_foreign_icu_and_nothing_else(self):
        entries = re.search(r"^\[InstallDelete\]\n(.*?)(?=^\[)", ISS, re.MULTILINE | re.DOTALL).group(1)
        lines = [l for l in entries.splitlines() if l.strip() and not l.lstrip().startswith(";")]
        assert lines == ['Type: files; Name: "{app}\\_internal\\icu*.dll"']
