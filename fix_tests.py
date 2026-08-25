import os
import re

for root, _, files in os.walk('tests'):
    for file in files:
        if not file.endswith('.py'):
            continue
        path = os.path.join(root, file)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        orig_content = content
        
        content = content.replace('DashboardWindow(mock_settings, icon_idle=', 'DashboardWindow(mock_settings, ModelProvider("."), icon_idle=')
        content = content.replace('DashboardWindow(settings=mock_settings, icon_idle=', 'DashboardWindow(settings=mock_settings, model_provider=ModelProvider("."), icon_idle=')
        
        content = content.replace('TrayApp(mock_settings)', 'TrayApp(mock_settings, ModelProvider("."))')
        content = content.replace('TrayApp(settings=mock_settings)', 'TrayApp(settings=mock_settings, model_provider=ModelProvider("."))')
        
        content = content.replace('TranscriptionWorker(mock_settings)', 'TranscriptionWorker(mock_settings, ModelProvider("."))')
        content = content.replace('TranscriptionWorker(settings=mock_settings)', 'TranscriptionWorker(settings=mock_settings, model_provider=ModelProvider("."))')
        
        if content != orig_content:
            if 'from core.models import ModelProvider' not in content:
                content = 'from core.models import ModelProvider\n' + content
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
