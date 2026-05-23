import pytest
from core.settings import SettingsManager

def test_settings_manager_handles_none_language():
    sm = SettingsManager(in_memory=True)
    sm.set("language", None) # "auto" olarak kaydedilmeli
    assert sm.get("language") is None # library için None dönmeli
