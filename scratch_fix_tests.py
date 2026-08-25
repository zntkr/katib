import os

path = 'tests/test_transcription_worker_logic.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('worker = TranscriptionWorker(mock_settings)', 'worker = TranscriptionWorker(mock_settings, MagicMock())')
content = content.replace('TranscriptionWorker(mock_settings)', 'TranscriptionWorker(mock_settings, MagicMock())')
content = content.replace('patch.object(mock_settings, "get_resolved_model_dir"', 'patch.object(worker.model_provider, "get_active_model_path"')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
