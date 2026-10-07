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
