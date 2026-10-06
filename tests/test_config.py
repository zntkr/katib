"""
Tests for core/settings.py: load_settings, save_settings, get/set_model_dir_setting,
validate_model_dir — full coverage. No Qt or hardware required.
"""
import json
import logging
from pathlib import Path
from unittest.mock import patch
import pytest
from core.settings import SettingsManager, get_settings_path

# shared fixture: get_settings_path → tmp_path

@pytest.fixture
def settings_file(tmp_path):
    """Redirects get_settings_path() calls into tmp_path.
    The real ~/.katib_app/settings.json is never touched."""
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
        sm.set("language", "en")
        sm.set("language", None)
        assert sm.get("language") is None
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data.get("language", "auto") == "auto"  # never persisted as null

    def test_compute_type_valid(self, settings_file):
        sm = SettingsManager()
        sm.set("compute_type", "int8")
        assert sm.get("compute_type") == "int8"

    def test_compute_type_invalid_falls_back(self, settings_file):
        sm = SettingsManager()
        sm.set("compute_type", "invalid")
        assert sm.get("compute_type") == "int8"

    def test_compute_device_defaults_to_auto(self, settings_file):
        assert SettingsManager().get("compute_device") == "auto"

    @pytest.mark.parametrize("value", ["auto", "cpu", "cuda"])
    def test_compute_device_valid(self, settings_file, value):
        sm = SettingsManager()
        sm.set("compute_device", value)
        assert sm.get("compute_device") == value

    def test_compute_device_invalid_falls_back(self, settings_file):
        sm = SettingsManager()
        sm.set("compute_device", "quantum")
        assert sm.get("compute_device") == "auto"

class TestDefaults:
    def test_transcription_language_defaults_to_auto(self):
        assert SettingsManager(in_memory=True).get("language") is None  # "auto"

    def test_app_language_defaults_to_system_detection(self):
        assert SettingsManager(in_memory=True).get("app_language") == ""

    def test_only_non_default_values_are_persisted(self, settings_file):
        sm = SettingsManager()
        sm.set("hotkey", "f10")
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data == {"hotkey": "f10"}

    def test_value_reset_to_default_is_dropped_from_file(self, settings_file):
        sm = SettingsManager()
        sm.set("hotkey", "f10")
        sm.set("hotkey", "F9")
        assert json.loads(settings_file.read_text(encoding="utf-8")) == {}

    def test_unknown_keys_are_kept(self, settings_file):
        settings_file.write_text(json.dumps({"from_a_newer_version": "kept"}), encoding="utf-8")
        sm = SettingsManager()
        sm.set("hotkey", "f10")
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["from_a_newer_version"] == "kept"

    def test_changed_default_reaches_existing_users(self, settings_file):
        from core import settings as settings_mod
        SettingsManager().set("hotkey", "f10")
        with patch.dict(settings_mod.DEFAULTS, {"injection_method": "new-default"}):
            assert SettingsManager().get("injection_method") == "new-default"

    def test_every_setting_the_app_reads_has_a_default(self):
        """DEFAULTS is the single list of settings: a key used in the code but missing here
        would silently read as None and always be written to settings.json."""
        import re
        from core.settings import DEFAULTS
        root = Path(__file__).resolve().parent.parent
        used = set()
        for folder in ("core", "workers", "ui"):
            for source in (root / folder).glob("*.py"):
                used.update(re.findall(r'settings\.(?:get|set)\(\s*"(\w+)"', source.read_text(encoding="utf-8")))
        assert used - set(DEFAULTS) == set()


# set_many

class TestSetMany:

    def test_empty_mapping_is_noop(self, settings_file):
        sm = SettingsManager()
        sm.set("hotkey", "f9")
        sm.set_many({})
        assert sm.get("hotkey") == "f9"

    def test_sets_multiple_keys_atomically(self, settings_file):
        sm = SettingsManager()
        sm.set_many({"hotkey": "f10", "injection_method": "keystroke"})
        sm2 = SettingsManager()
        assert sm2.get("hotkey") == "f10"
        assert sm2.get("injection_method") == "keystroke"

    def test_language_none_stored_as_auto(self, settings_file):
        sm = SettingsManager()
        sm.set_many({"language": "en"})
        sm.set_many({"language": None})
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data.get("language", "auto") == "auto"  # never persisted as null

    def test_single_save_call_for_multiple_keys(self, settings_file):
        """set_many() calls save() exactly once regardless of how many keys it contains."""
        from unittest.mock import patch
        sm = SettingsManager()
        with patch.object(sm, "save") as mock_save:
            sm.set_many({"hotkey": "f10", "language": "tr", "compute_type": "int8"})
        assert mock_save.call_count == 1

    def test_empty_mapping_does_not_call_save(self, settings_file):
        """set_many() called with an empty dict must never trigger save()."""
        from unittest.mock import patch
        sm = SettingsManager()
        with patch.object(sm, "save") as mock_save:
            sm.set_many({})
        assert mock_save.call_count == 0

    def test_in_memory_set_many_does_not_write_to_disk(self):
        """set_many() must not write to disk in in_memory=True mode."""
        from unittest.mock import patch
        sm = SettingsManager(in_memory=True)
        with patch("core.settings.get_settings_path") as mock_path:
            sm.set_many({"hotkey": "f10", "compute_type": "float32"})
        mock_path.assert_not_called()
        assert sm.get("hotkey") == "f10"
