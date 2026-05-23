import json
import pytest
from pathlib import Path
from core.i18n import available_languages, _translations_dir

def test_available_languages_includes_korean():
    """Verify that available languages contains Korean mapped to 한국어."""
    langs = available_languages()
    lang_codes = [code for _, code in langs]
    lang_names = [name for name, _ in langs]
    
    assert "ko" in lang_codes
    assert "한국어" in lang_names
    # Verify that English and Turkish are also present
    assert "en" in lang_codes
    assert "tr" in lang_codes

def test_translation_files_integrity_and_key_parity():
    """Verify that all JSON translation files are valid and contain identical key structures as en.json."""
    trans_dir = _translations_dir()
    en_path = trans_dir / "en.json"
    
    with open(en_path, "r", encoding="utf-8") as f:
        en_data = json.load(f)
        
    def get_all_keys(data, prefix=""):
        keys = set()
        if isinstance(data, dict):
            for k, v in data.items():
                full_key = f"{prefix}.{k}" if prefix else k
                keys.add(full_key)
                keys.update(get_all_keys(v, full_key))
        return keys

    en_keys = get_all_keys(en_data)
    
    # Iterate over all JSON files in the translations directory
    json_files = list(trans_dir.glob("*.json"))
    assert len(json_files) > 0
    
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            try:
                lang_data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Translation file {json_file.name} is not a valid JSON: {e}")
                
        lang_keys = get_all_keys(lang_data)
        
        # Verify that the keys are identical
        missing_keys = en_keys - lang_keys
        extra_keys = lang_keys - en_keys
        
        assert not missing_keys, f"{json_file.name} is missing keys: {missing_keys}"
        assert not extra_keys, f"{json_file.name} has extra keys: {extra_keys}"
