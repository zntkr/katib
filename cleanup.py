import os
import re

# Remove from core/settings.py
with open('core/settings.py', 'r', encoding='utf-8') as f:
    settings_content = f.read()

settings_content = re.sub(r'def validate_model_dir\(path: str \| None\) -> str \| None:.*?return None\n\n\n', '', settings_content, flags=re.DOTALL)
settings_content = re.sub(r'def find_fallback_model_dir\(parent_path: Path\) -> str \| None:.*?return None\n\n\n', '', settings_content, flags=re.DOTALL)
settings_content = re.sub(r'    def get_resolved_model_dir\(self\) -> str \| None:.*?return None\n\n', '', settings_content, flags=re.DOTALL)

with open('core/settings.py', 'w', encoding='utf-8') as f:
    f.write(settings_content)

# Remove from tests/test_model_resolution.py
with open('tests/test_model_resolution.py', 'r', encoding='utf-8') as f:
    tmr_content = f.read()

tmr_content = re.sub(r'from core.settings import find_fallback_model_dir\n\n', '', tmr_content)
tmr_content = re.sub(r'def test_find_fallback_model_dir_finds_valid_model.*?assert result is None\n\n', '', tmr_content, flags=re.DOTALL)
tmr_content = re.sub(r'def test_settings_manager_resolves_fallback_and_updates_settings.*?assert sm\.get\("model_dir"\) == str\(model_dir\.resolve\(\)\)\n\n', '', tmr_content, flags=re.DOTALL)

with open('tests/test_model_resolution.py', 'w', encoding='utf-8') as f:
    f.write(tmr_content)

# Remove from tests/test_config.py
with open('tests/test_config.py', 'r', encoding='utf-8') as f:
    tc_content = f.read()

tc_content = tc_content.replace(', validate_model_dir, find_fallback_model_dir, get_settings_path', ', get_settings_path')
tc_content = re.sub(r'# validate_model_dir\n.*?# get_resolved_model_dir', '# get_resolved_model_dir', tc_content, flags=re.DOTALL)
tc_content = re.sub(r'    def test_get_resolved_model_dir_valid_dir_returns_path\(self, tmp_path\):.*', '', tc_content, flags=re.DOTALL)

with open('tests/test_config.py', 'w', encoding='utf-8') as f:
    f.write(tc_content)
