"""
core/settings.py testleri: load_settings, save_settings, get/set_model_dir_setting,
validate_model_dir — tam kapsam. Qt veya donanım gerektirmez.
"""
import json
import logging
from pathlib import Path
from unittest.mock import patch
import pytest
from core.settings import SettingsManager, validate_model_dir, find_fallback_model_dir, get_settings_path

# ── shared fixture: get_settings_path → tmp_path ────────────────────────────

@pytest.fixture
def settings_file(tmp_path):
    """get_settings_path() çağrısını tmp_path içine yönlendirir.
    Gerçek ~/.katib_app/settings.json dosyasına dokunulmaz."""
    path = tmp_path / "settings.json"
    with patch("core.settings.get_settings_path", return_value=path):
        yield path


class TestSettingsManager:
    def test_in_memory(self):
        sm = SettingsManager(in_memory=True)
        sm.set("hotkey", "f10")
        assert sm.get("hotkey") == "f10"
        
    def test_load_save(self, settings_file):
        sm = SettingsManager()
        sm.set("hotkey", "f10")
        
        # New instance should load from file
        sm2 = SettingsManager()
        assert sm2.get("hotkey") == "f10"
        
    def test_corrupt_json_handled(self, settings_file, caplog):
        settings_file.write_text("{bad", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="core.settings"):
            sm = SettingsManager()
        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert sm.get("hotkey") == "F9" # default

    def test_language_auto_conversion(self, settings_file):
        sm = SettingsManager()
        sm.set("language", None)
        assert sm.get("language") is None
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["language"] == "auto"

    def test_compute_type_valid(self, settings_file):
        sm = SettingsManager()
        sm.set("compute_type", "int8")
        assert sm.get("compute_type") == "int8"

    def test_compute_type_invalid_falls_back(self, settings_file):
        sm = SettingsManager()
        sm.set("compute_type", "invalid")
        assert sm.get("compute_type") == "int8"

    def test_reset_processing_settings(self, settings_file):
        sm = SettingsManager()
        sm.set("language", "auto")
        sm.reset_processing_settings()
        assert sm.get("language") == "tr"  # default'a döner


# ──────────────────────────────────────── validate_model_dir ────────────────

def _make_model_dir(base: Path, use_safetensors: bool = False) -> Path:
    """base içinde geçerli bir Whisper model dizini oluşturur."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "config.json").write_text("{}")
    (base / ("model.safetensors" if use_safetensors else "model.bin")).write_bytes(b"")
    return base


class TestValidateModelDirBasic:

    def test_none_returns_none(self):
        assert validate_model_dir(None) is None

    def test_empty_string_returns_none(self):
        assert validate_model_dir("") is None

    def test_nonexistent_path_returns_none(self):
        assert validate_model_dir("/nonexistent/xyz/abc") is None

    def test_file_path_returns_none(self, tmp_path):
        f = tmp_path / "model.bin"
        f.write_bytes(b"")
        assert validate_model_dir(str(f)) is None

    def test_returns_string_type(self, tmp_path):
        _make_model_dir(tmp_path)
        assert isinstance(validate_model_dir(str(tmp_path)), str)


class TestValidateModelDirDirect:
    """Doğrudan model dizini: config.json + model.bin/safetensors aynı klasörde."""

    def test_detects_model_bin(self, tmp_path):
        _make_model_dir(tmp_path)
        assert validate_model_dir(str(tmp_path)) == str(tmp_path)

    def test_detects_safetensors(self, tmp_path):
        _make_model_dir(tmp_path, use_safetensors=True)
        assert validate_model_dir(str(tmp_path)) == str(tmp_path)

    def test_missing_config_json_falls_through_to_walk(self, tmp_path):
        (tmp_path / "model.bin").write_bytes(b"")
        # config.json yok → doğrudan kabul yok; os.walk de bulamaz
        assert validate_model_dir(str(tmp_path)) is None

    def test_missing_model_file_falls_through_to_walk(self, tmp_path):
        (tmp_path / "config.json").write_text("{}")
        assert validate_model_dir(str(tmp_path)) is None

    def test_empty_dir_returns_none(self, tmp_path):
        assert validate_model_dir(str(tmp_path)) is None


class TestValidateModelDirWalk:
    """Ana klasör seçildiğinde alt dizinlerde model arama (os.walk)."""

    def test_finds_model_at_depth_1(self, tmp_path):
        model_dir = _make_model_dir(tmp_path / "model")
        assert validate_model_dir(str(tmp_path)) == str(model_dir.resolve())

    def test_finds_model_at_depth_2(self, tmp_path):
        model_dir = _make_model_dir(tmp_path / "a" / "model")
        assert validate_model_dir(str(tmp_path)) == str(model_dir.resolve())

    def test_finds_model_at_depth_3(self, tmp_path):
        model_dir = _make_model_dir(tmp_path / "a" / "b" / "model")
        assert validate_model_dir(str(tmp_path)) == str(model_dir.resolve())

    def test_finds_model_at_depth_4(self, tmp_path):
        model_dir = _make_model_dir(tmp_path / "a" / "b" / "c" / "model")
        assert validate_model_dir(str(tmp_path)) == str(model_dir.resolve())

    def test_does_not_find_model_at_depth_5(self, tmp_path):
        _make_model_dir(tmp_path / "a" / "b" / "c" / "d" / "model")
        assert validate_model_dir(str(tmp_path)) is None

    def test_finds_safetensors_in_subdir(self, tmp_path):
        model_dir = _make_model_dir(tmp_path / "sub", use_safetensors=True)
        assert validate_model_dir(str(tmp_path)) == str(model_dir.resolve())

    def test_no_model_in_any_subdir_returns_none(self, tmp_path):
        (tmp_path / "a" / "b").mkdir(parents=True)
        assert validate_model_dir(str(tmp_path)) is None

    def test_oserror_during_walk_returns_none(self, tmp_path):
        with patch("os.walk", side_effect=OSError("erişim reddedildi")):
            assert validate_model_dir(str(tmp_path)) is None


class TestValidateModelDirDepthLimit:
    """Derinlik limiti: depth > 4 olduğunda dizin taranmayı durdurmalı."""

    def test_model_at_exact_depth_4_is_found(self, tmp_path):
        model_dir = _make_model_dir(tmp_path / "l1" / "l2" / "l3" / "model")
        assert validate_model_dir(str(tmp_path)) == str(model_dir.resolve())

    def test_model_beyond_depth_4_is_not_found(self, tmp_path):
        _make_model_dir(tmp_path / "l1" / "l2" / "l3" / "l4" / "model")
        assert validate_model_dir(str(tmp_path)) is None

    def test_shallower_model_found_despite_deep_sibling(self, tmp_path):
        """Derinlik sınırını aşan dal varken, sığ daldaki model bulunmalı."""
        _make_model_dir(tmp_path / "l1" / "l2" / "l3" / "l4" / "too_deep")
        model_dir = _make_model_dir(tmp_path / "shallow" / "model")
        assert validate_model_dir(str(tmp_path)) == str(model_dir.resolve())


# ──────────────────────────────────── get_settings_path ────────────────────

class TestGetSettingsPath:

    def test_returns_path_under_home(self, tmp_path):
        with patch("core.settings.Path.home", return_value=tmp_path):
            result = get_settings_path()
        assert result == tmp_path / ".katib_app" / "settings.json"

    def test_creates_parent_dir(self, tmp_path):
        with patch("core.settings.Path.home", return_value=tmp_path):
            result = get_settings_path()
        assert result.parent.is_dir()


# ──────────────────────────────── find_fallback_model_dir ──────────────────

class TestFindFallbackModelDir:

    def test_nonexistent_parent_returns_none(self, tmp_path):
        assert find_fallback_model_dir(tmp_path / "nope") is None

    def test_file_path_returns_none(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("")
        assert find_fallback_model_dir(f) is None

    def test_parent_itself_is_valid_model(self, tmp_path):
        _make_model_dir(tmp_path)
        assert find_fallback_model_dir(tmp_path) == str(tmp_path)

    def test_finds_model_in_subdirectory(self, tmp_path):
        model = _make_model_dir(tmp_path / "faster-whisper-small")
        result = find_fallback_model_dir(tmp_path)
        assert result == str(model.resolve())

    def test_no_model_anywhere_returns_none(self, tmp_path):
        (tmp_path / "empty").mkdir()
        assert find_fallback_model_dir(tmp_path) is None

    def test_oserror_during_iteration_returns_none(self, tmp_path):
        with patch("core.settings.Path.iterdir", side_effect=OSError("erişim reddedildi")):
            assert find_fallback_model_dir(tmp_path) is None

    def test_finds_model_in_subdir_beyond_parent_walk_depth(self, tmp_path):
        # Depth 5 from tmp_path → validate_model_dir(tmp_path) None döner (limit 4)
        # Depth 4 from tmp_path/a → validate_model_dir(tmp_path/a) bulur → line 150
        model = _make_model_dir(tmp_path / "a" / "b" / "c" / "d" / "model")
        result = find_fallback_model_dir(tmp_path)
        assert result == str(model.resolve())


# ──────────────────────────── SettingsManager I/O hataları ─────────────────

class TestSettingsManagerIOErrors:

    def test_load_oserror_uses_defaults(self, tmp_path, caplog):
        path = tmp_path / "settings.json"
        path.write_text('{"hotkey": "f5"}', encoding="utf-8")
        with patch("core.settings.get_settings_path", return_value=path), \
             patch("builtins.open", side_effect=OSError("erişim reddedildi")):
            with caplog.at_level(logging.ERROR, logger="core.settings"):
                sm = SettingsManager()
        assert sm.get("hotkey") == "F9"
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_save_oserror_logs_error(self, tmp_path, caplog):
        path = tmp_path / "settings.json"
        with patch("core.settings.get_settings_path", return_value=path):
            sm = SettingsManager()
            with patch("builtins.open", side_effect=OSError("disk dolu")):
                with caplog.at_level(logging.ERROR, logger="core.settings"):
                    sm.set("hotkey", "f5")
        assert any(r.levelno == logging.ERROR for r in caplog.records)


# ──────────────────────── get_resolved_model_dir fallback ──────────────────

class TestGetResolvedModelDir:

    def test_returns_valid_model_dir(self, tmp_path, settings_file):
        model = _make_model_dir(tmp_path / "model")
        sm = SettingsManager()
        sm.set("model_dir", str(model))
        assert sm.get_resolved_model_dir() == str(model)

    def test_invalid_model_dir_triggers_fallback(self, tmp_path, settings_file):
        model = _make_model_dir(tmp_path / "fallback-model")
        sm = SettingsManager()
        sm.set("model_dir", "/nonexistent/path")
        with patch("core.settings.find_fallback_model_dir", return_value=str(model)):
            result = sm.get_resolved_model_dir()
        assert result == str(model)

    def test_fallback_saves_model_dir(self, tmp_path, settings_file):
        model = _make_model_dir(tmp_path / "fallback-model")
        sm = SettingsManager()
        sm.set("model_dir", "/nonexistent/path")
        with patch("core.settings.find_fallback_model_dir", return_value=str(model)):
            sm.get_resolved_model_dir()
        assert sm.get("model_dir") == str(model)

    def test_no_model_anywhere_returns_none(self, settings_file):
        sm = SettingsManager()
        sm.set("model_dir", "/nonexistent")
        with patch("core.settings.find_fallback_model_dir", return_value=None):
            assert sm.get_resolved_model_dir() is None


# ──────────────────────────────── set_many ─────────────────────────────────

class TestSetMany:

    def test_empty_mapping_is_noop(self, settings_file):
        sm = SettingsManager()
        sm.set("hotkey", "f9")
        sm.set_many({})
        assert sm.get("hotkey") == "f9"

    def test_sets_multiple_keys_atomically(self, settings_file):
        sm = SettingsManager()
        sm.set_many({"hotkey": "f10", "beam_size": 3})
        sm2 = SettingsManager()
        assert sm2.get("hotkey") == "f10"
        assert sm2.get("beam_size") == 3

    def test_language_none_stored_as_auto(self, settings_file):
        sm = SettingsManager()
        sm.set_many({"language": None})
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["language"] == "auto"

    def test_single_save_call_for_multiple_keys(self, settings_file):
        """set_many(), kaç anahtar içerirse içersin save() yalnızca bir kez çağrılır."""
        from unittest.mock import patch
        sm = SettingsManager()
        with patch.object(sm, "save") as mock_save:
            sm.set_many({"hotkey": "f10", "language": "tr", "compute_type": "int8"})
        assert mock_save.call_count == 1

    def test_empty_mapping_does_not_call_save(self, settings_file):
        """set_many() boş dict ile çağrılırsa save() hiç tetiklenmez."""
        from unittest.mock import patch
        sm = SettingsManager()
        with patch.object(sm, "save") as mock_save:
            sm.set_many({})
        assert mock_save.call_count == 0

    def test_in_memory_set_many_does_not_write_to_disk(self):
        """in_memory=True modunda set_many() disk yazımı yapmaz."""
        from unittest.mock import patch
        sm = SettingsManager(in_memory=True)
        with patch("core.settings.get_settings_path") as mock_path:
            sm.set_many({"hotkey": "f10", "compute_type": "float32"})
        mock_path.assert_not_called()
        assert sm.get("hotkey") == "f10"
