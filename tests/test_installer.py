"""Katib.iss: the program must stay out of the folder that holds the user's settings and
models, and the uninstaller must not delete anything it did not install (ADR-0014).

These read the script; they do not run Setup (plan 0011 Faz 2 does, by hand)."""
import os
import re
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

import pytest

from core import settings

SCRIPT = (Path(__file__).resolve().parent.parent / "Katib.iss").read_text(encoding="utf-8")
LOCAL = PureWindowsPath(r"C:\Users\someone\AppData\Local")


def _defines() -> dict[str, str]:
    return dict(re.findall(r'^#define\s+(\w+)\s+"(.*)"\s*$', SCRIPT, flags=re.MULTILINE))


def _section(name: str) -> list[str]:
    """The entries of one section, without blank lines and comments."""
    match = re.search(rf"^\[{name}\]\n(.*?)(?=^\[|\Z)", SCRIPT, flags=re.MULTILINE | re.DOTALL)
    lines = match.group(1).splitlines() if match else []
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith((";", "//"))]


def _setup() -> dict[str, str]:
    return dict(line.split("=", 1) for line in _section("Setup"))


def _expand(text: str) -> PureWindowsPath:
    """What Setup makes of a path for a per-user install (PrivilegesRequired=lowest)."""
    for _ in range(3):  # a define may use another define
        for name, value in _defines().items():
            text = text.replace("{#" + name + "}", value)
    text = text.replace("{autopf}", str(LOCAL / "Programs")).replace("{localappdata}", str(LOCAL))
    assert "{" not in text, f"unexpanded constant in {text}"
    return PureWindowsPath(text)


class TestInstallLocation:
    def test_the_script_knows_the_real_data_folder(self):
        """If the app's data folder ever moves, the installer's guard must move with it."""
        with patch("sys.platform", "win32"), patch.dict(os.environ, {"LOCALAPPDATA": str(LOCAL)}):
            assert _expand("{#DataDir}") == PureWindowsPath(settings.get_app_data_dir())

    def test_the_program_is_not_installed_into_the_data_folder(self):
        target, data = _expand(_setup()["DefaultDirName"]), _expand("{#DataDir}")
        assert target != data and data not in target.parents

    def test_the_default_is_the_per_user_programs_folder(self):
        assert _setup()["PrivilegesRequired"] == "lowest"
        assert _expand(_setup()["DefaultDirName"]) == LOCAL / "Programs" / "Katib"

    def test_the_program_always_goes_to_that_one_folder(self):
        """Setup does not ask for a folder, and does not reuse the folder of an older
        install: 1.0.0 lived in the data folder and Setup would otherwise stay there."""
        assert _setup().get("DisableDirPage") == "yes"
        assert _setup().get("UsePreviousAppDir") == "no"


class TestUninstall:
    def test_nothing_is_deleted_beyond_what_setup_installed(self):
        assert _section("UninstallDelete") == []
        assert "filesandordirs" not in SCRIPT

    @pytest.mark.parametrize("section", ["InstallDelete", "UninstallDelete", "Dirs", "Files"])
    def test_no_entry_writes_to_or_deletes_from_the_data_folder(self, section):
        assert [line for line in _section(section) if "DataDir" in line or "{localappdata}" in line] == []

    def test_the_script_deletes_nothing_by_its_own_code(self):
        code = "\n".join(_section("Code"))
        assert re.findall(r"\b(DelTree|DeleteFile|RemoveDir)\b", code) == []

    def test_the_only_code_is_the_note_about_the_data_folder(self):
        code = "\n".join(_section("Code"))
        assert re.findall(r"^(?:procedure|function)\s+(\w+)", code, flags=re.MULTILINE) == ["CurUninstallStepChanged"]
