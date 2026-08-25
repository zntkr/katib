import pytest
from pathlib import Path
def test_transcription_worker_uses_resolved_model_dir(tmp_path):
    from workers.transcription_worker import TranscriptionWorker
    from core.settings import SettingsManager
    from unittest.mock import MagicMock, patch
    
    # Mock settings
    sm = SettingsManager(in_memory=True)
    sm.set("model_dir", str(tmp_path))
    
    # Create a TranscriptionWorker and test _load_model without starting a thread
    from core.models import ModelProvider
    mock_provider = MagicMock(spec=ModelProvider)
    mock_provider.get_active_model_path.return_value = str(tmp_path)
    worker = TranscriptionWorker(settings=sm, model_provider=mock_provider)
    
    import sys
    sys.modules["faster_whisper"] = MagicMock()
    
    import sys
    mock_fw = MagicMock()
    sys.modules["faster_whisper"] = mock_fw
    
    worker._load_model()
    
    # Verify that model_provider.get_active_model_path was called
    mock_provider.get_active_model_path.assert_called_once()
    
    # Verify that WhisperModel was initialized with the resolved directory
    mock_fw.WhisperModel.assert_called()
    args, kwargs = mock_fw.WhisperModel.call_args
    assert args[0] == str(tmp_path)


