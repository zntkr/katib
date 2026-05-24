import pytest
from pathlib import Path
from core.settings import find_fallback_model_dir

def test_find_fallback_model_dir_finds_valid_model(tmp_path):
    # Create a valid model structure inside a subdirectory
    model_dir = tmp_path / "author" / "whisper-model"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}")
    (model_dir / "model.bin").write_text("")
    
    # Create an empty sibling directory
    (tmp_path / "empty_dir").mkdir()
    
    # Run the function against the root directory (tmp_path)
    result = find_fallback_model_dir(tmp_path)
    
    assert result is not None
    assert Path(result).resolve() == model_dir.resolve()

def test_find_fallback_model_dir_returns_none_if_no_valid_model(tmp_path):
    # Create an invalid structure (model.bin is missing)
    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    (invalid_dir / "config.json").write_text("{}")
    
    result = find_fallback_model_dir(tmp_path)
    assert result is None

def test_settings_manager_resolves_fallback_and_updates_settings(tmp_path):
    from core.settings import SettingsManager, DEFAULT_DOWNLOAD_PARENT
    from unittest.mock import patch
    
    # Mock settings manager in-memory
    sm = SettingsManager(in_memory=True)
    
    # Assign an invalid model directory
    sm.set("model_dir", "/nonexistent/path")
    
    # Create a valid fallback directory
    fallback_parent = tmp_path / "models"
    fallback_parent.mkdir()
    model_dir = fallback_parent / "author" / "whisper-small"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}")
    (model_dir / "model.bin").write_text("")
    
    # Redirect DEFAULT_DOWNLOAD_PARENT to the temporary directory
    with patch("core.settings.DEFAULT_DOWNLOAD_PARENT", fallback_parent):
        resolved = sm.get_resolved_model_dir()
        
        assert resolved is not None
        assert Path(resolved).resolve() == model_dir.resolve()
        # Verify that the settings were updated
        assert sm.get("model_dir") == str(model_dir.resolve())

def test_transcription_worker_uses_resolved_model_dir(tmp_path):
    from workers.transcription_worker import TranscriptionWorker
    from core.settings import SettingsManager
    from unittest.mock import MagicMock, patch
    
    # Mock settings
    sm = SettingsManager(in_memory=True)
    sm.get_resolved_model_dir = MagicMock(return_value=str(tmp_path))
    
    # Create a TranscriptionWorker and test _load_model without starting a thread
    worker = TranscriptionWorker(settings=sm)
    
    import sys
    sys.modules["faster_whisper"] = MagicMock()
    
    import sys
    mock_fw = MagicMock()
    sys.modules["faster_whisper"] = mock_fw
    
    worker._load_model()
    
    # Verify that get_resolved_model_dir was called
    sm.get_resolved_model_dir.assert_called_once()
    
    # Verify that WhisperModel was initialized with the resolved directory
    mock_fw.WhisperModel.assert_called()
    args, kwargs = mock_fw.WhisperModel.call_args
    assert args[0] == str(tmp_path)


