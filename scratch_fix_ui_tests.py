import os

def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "from core.models import ModelProvider" not in content:
        content = "from core.models import ModelProvider\n" + content

    content = content.replace('patch("ui.settings_dialog.validate_model_dir"', 'patch("core.models.ModelProvider.resolve_model_dir"')
    
    content = content.replace('SettingsDialog(mock_settings)', 'SettingsDialog(mock_settings, ModelProvider("."))')
    content = content.replace('SettingsDialog(settings=mock_settings, parent=None)', 'SettingsDialog(settings=mock_settings, model_provider=ModelProvider("."), parent=None)')
    content = content.replace('SettingsDialog(mock_settings, parent=self.dashboard)', 'SettingsDialog(mock_settings, ModelProvider("."), parent=self.dashboard)')
    content = content.replace('SettingsDialog(mock_settings, parent=dashboard)', 'SettingsDialog(mock_settings, ModelProvider("."), parent=dashboard)')
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

fix_file('tests/test_ui_interactions.py')
fix_file('tests/test_dialogs.py')
