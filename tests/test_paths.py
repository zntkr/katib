"""
Tests for the app data path resolvers and the legacy data migration.
Does not require Qt or hardware.
"""
import os
import sys
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from core import settings
from ui.utils import qt_key_to_keyboard, _make_icon

class TestSettingsPath:
    def test_returns_path_object(self):
        assert isinstance(settings.get_settings_path(), Path)

    def test_is_absolute(self):
        assert settings.get_settings_path().is_absolute()

    def test_ends_with_settings_json(self):
        assert settings.get_settings_path().name == "settings.json"

    def test_points_to_app_data_dir(self):
        expected = settings.get_app_data_dir() / "settings.json"
        assert settings.get_settings_path() == expected


class TestAppDataDir:
    """ADR-0009: settings, models and logs share a single root."""

    def test_windows_uses_localappdata(self, tmp_path):
        with patch("sys.platform", "win32"), \
             patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}):
            assert settings.get_app_data_dir() == tmp_path / "Katib"

    def test_windows_without_localappdata_uses_default_location(self, tmp_path):
        env = {k: v for k, v in os.environ.items() if k != "LOCALAPPDATA"}
        with patch("sys.platform", "win32"), \
             patch.dict(os.environ, env, clear=True), \
             patch("core.settings.Path.home", return_value=tmp_path):
            assert settings.get_app_data_dir() == tmp_path / "AppData" / "Local" / "Katib"

    def test_linux_uses_xdg_data_home(self, tmp_path):
        with patch("sys.platform", "linux"), \
             patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            assert settings.get_app_data_dir() == tmp_path / "Katib"

    def test_linux_without_xdg_uses_local_share(self, tmp_path):
        env = {k: v for k, v in os.environ.items() if k != "XDG_DATA_HOME"}
        with patch("sys.platform", "linux"), \
             patch.dict(os.environ, env, clear=True), \
             patch("core.settings.Path.home", return_value=tmp_path):
            assert settings.get_app_data_dir() == tmp_path / ".local" / "share" / "Katib"

    def test_settings_models_and_logs_share_one_root(self):
        root = settings.get_app_data_dir()
        assert settings.get_settings_path().parent == root
        assert settings.DEFAULT_DOWNLOAD_PARENT == root / "Models"
        assert settings.get_log_dir() == root / "Logs"


class TestLegacyMigration:
    """One-time move of pre-ADR-0009 data out of ~/.katib_app."""

    @staticmethod
    def _make_model(path: Path) -> Path:
        path.mkdir(parents=True)
        (path / "config.json").write_text("{}")
        (path / "model.bin").write_bytes(b"\0")
        return path

    @pytest.fixture
    def dirs(self, tmp_path):
        legacy = tmp_path / "home" / ".katib_app"
        app = tmp_path / "AppData" / "Local" / "Katib"
        return legacy, app

    def _migrate(self, dirs):
        legacy, app = dirs
        settings.migrate_legacy_data(legacy_dir=legacy, app_dir=app)

    def _read_settings(self, app: Path) -> dict:
        return json.loads((app / "settings.json").read_text(encoding="utf-8"))

    def test_no_legacy_dir_is_noop(self, dirs):
        _, app = dirs
        self._migrate(dirs)
        assert not app.exists()

    def test_moves_models_and_settings(self, dirs):
        legacy, app = dirs
        old_model = self._make_model(legacy / "models" / "faster-whisper-small")
        (legacy / "settings.json").write_text(json.dumps({"hotkey": "f8", "model_dir": str(old_model)}))

        self._migrate(dirs)

        new_model = app / "Models" / "faster-whisper-small"
        assert (new_model / "model.bin").exists()
        data = self._read_settings(app)
        assert data["hotkey"] == "f8"
        assert Path(data["model_dir"]) == new_model
        assert not legacy.exists()

    def test_old_default_model_dir_is_rewritten_to_new_default(self, dirs):
        legacy, app = dirs
        self._make_model(legacy / "models" / "faster-whisper-small")
        (legacy / "settings.json").write_text(json.dumps({"model_dir": str(legacy / "models")}))

        self._migrate(dirs)

        assert Path(self._read_settings(app)["model_dir"]) == app / "Models"

    def test_custom_model_dir_outside_legacy_is_kept(self, dirs, tmp_path):
        legacy, app = dirs
        custom = str(tmp_path / "D" / "my-model")
        legacy.mkdir(parents=True)
        (legacy / "settings.json").write_text(json.dumps({"model_dir": custom}))

        self._migrate(dirs)

        assert self._read_settings(app)["model_dir"] == custom

    def test_existing_new_settings_are_not_overwritten(self, dirs):
        legacy, app = dirs
        legacy.mkdir(parents=True)
        (legacy / "settings.json").write_text(json.dumps({"hotkey": "old"}))
        app.mkdir(parents=True)
        (app / "settings.json").write_text(json.dumps({"hotkey": "new"}))

        self._migrate(dirs)

        assert self._read_settings(app)["hotkey"] == "new"

    def test_model_already_in_new_location_is_not_overwritten(self, dirs):
        legacy, app = dirs
        self._make_model(legacy / "models" / "faster-whisper-small")
        sideloaded = self._make_model(app / "Models" / "faster-whisper-small")
        (sideloaded / "marker").write_text("sideloaded")
        self._make_model(legacy / "models" / "faster-whisper-base")

        self._migrate(dirs)

        assert (sideloaded / "marker").exists()
        assert (app / "Models" / "faster-whisper-base" / "model.bin").exists()

    def test_failed_move_keeps_legacy_model_usable(self, dirs):
        legacy, app = dirs
        old_model = self._make_model(legacy / "models" / "faster-whisper-small")
        (legacy / "settings.json").write_text(json.dumps({"model_dir": str(legacy / "models")}))

        with patch("core.settings.os.rename", side_effect=OSError("locked")):
            self._migrate(dirs)

        assert (old_model / "model.bin").exists()
        # The Models scan only covers the new directory, so model_dir must name the
        # model left behind, otherwise the app would report "model not found".
        assert Path(self._read_settings(app)["model_dir"]) == old_model

    def test_corrupt_legacy_settings_are_moved_as_is(self, dirs):
        legacy, app = dirs
        legacy.mkdir(parents=True)
        (legacy / "settings.json").write_text("{not json")

        self._migrate(dirs)

        assert (app / "settings.json").read_text() == "{not json"

    def test_never_raises(self, dirs):
        legacy, _ = dirs
        legacy.mkdir(parents=True)
        with patch("core.settings.Path.mkdir", side_effect=PermissionError("denied")):
            self._migrate(dirs)  # must not crash app startup


class TestEnterpriseGuide:
    """The deployment guide must describe the paths the code actually scans."""

    GUIDE = Path(__file__).resolve().parent.parent / "docs" / "guides" / "enterprise_deployment.md"

    def test_guide_uses_app_data_models_dir(self):
        text = self.GUIDE.read_text(encoding="utf-8")
        assert "%LOCALAPPDATA%\\Katib\\Models" in text
        assert "%USERPROFILE%" not in text
        assert ".katib_app" not in text

    def test_guide_model_folder_names_match_code(self):
        text = self.GUIDE.read_text(encoding="utf-8")
        for info in settings.WHISPER_MODELS.values():
            assert info["repo_id"].split("/")[-1] in text
        assert "systran-faster-whisper" not in text.lower()


class TestQtKeyToKeyboard:
    def test_f1_key(self, qapp):
        from PySide6.QtCore import Qt
        assert qt_key_to_keyboard(Qt.Key.Key_F1.value) == "f1"

    def test_f12_key(self, qapp):
        from PySide6.QtCore import Qt
        assert qt_key_to_keyboard(Qt.Key.Key_F12.value) == "f12"

    def test_space_key(self, qapp):
        from PySide6.QtCore import Qt
        assert qt_key_to_keyboard(Qt.Key.Key_Space.value) == "space"

    def test_escape_key(self, qapp):
        from PySide6.QtCore import Qt
        assert qt_key_to_keyboard(Qt.Key.Key_Escape.value) == "esc"

    def test_printable_ascii(self, qapp):
        assert qt_key_to_keyboard(ord("A")) == "a"

    def test_unknown_key_returns_none(self, qapp):
        assert qt_key_to_keyboard(0xFFFF) is None


class TestMakeIcon:
    def test_returns_qicon(self, qapp):
        from PySide6.QtGui import QIcon
        icon = _make_icon("#FF0000")
        assert isinstance(icon, QIcon)

    def test_icon_not_null(self, qapp):
        icon = _make_icon("#00FF00")
        assert not icon.isNull()
