import pytest
from core.settings import SettingsManager

def test_settings_manager_handles_none_language():
    sm = SettingsManager(in_memory=True)
    sm.set("language", None) # should be saved as "auto"
    assert sm.get("language") is None # should return None for the library
