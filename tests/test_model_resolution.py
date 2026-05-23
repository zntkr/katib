import pytest
from pathlib import Path
from core.settings import find_fallback_model_dir

def test_find_fallback_model_dir_finds_valid_model(tmp_path):
    # Bir alt dizinde geçerli bir model yapısı oluştur
    model_dir = tmp_path / "author" / "whisper-model"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}")
    (model_dir / "model.bin").write_text("")
    
    # Boş bir yan dizin oluştur
    (tmp_path / "empty_dir").mkdir()
    
    # Fonksiyonu ana dizin (tmp_path) üzerinde çalıştır
    result = find_fallback_model_dir(tmp_path)
    
    assert result is not None
    assert Path(result).resolve() == model_dir.resolve()

def test_find_fallback_model_dir_returns_none_if_no_valid_model(tmp_path):
    # Geçersiz bir yapı oluştur (model.bin eksik)
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
    
    # Geçersiz bir model dizini ata
    sm.set("model_dir", "/nonexistent/path")
    
    # Geçerli bir fallback dizini oluştur
    fallback_parent = tmp_path / "models"
    fallback_parent.mkdir()
    model_dir = fallback_parent / "author" / "whisper-small"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}")
    (model_dir / "model.bin").write_text("")
    
    # DEFAULT_DOWNLOAD_PARENT'ı geçici dizine yönlendir
    with patch("core.settings.DEFAULT_DOWNLOAD_PARENT", fallback_parent):
        resolved = sm.get_resolved_model_dir()
        
        assert resolved is not None
        assert Path(resolved).resolve() == model_dir.resolve()
        # Ayarların güncellendiğini doğrula
        assert sm.get("model_dir") == str(model_dir.resolve())

def test_transcription_worker_uses_resolved_model_dir(tmp_path):
    from workers.transcription_worker import TranscriptionWorker
    from core.settings import SettingsManager
    from unittest.mock import MagicMock, patch
    
    # Mock settings
    sm = SettingsManager(in_memory=True)
    sm.get_resolved_model_dir = MagicMock(return_value=str(tmp_path))
    
    # TranscriptionWorker oluştur (threading başlatmadan _load_model test edeceğiz)
    worker = TranscriptionWorker(settings=sm)
    
    import sys
    sys.modules["faster_whisper"] = MagicMock()
    
    import sys
    mock_fw = MagicMock()
    sys.modules["faster_whisper"] = mock_fw
    
    worker._load_model()
    
    # get_resolved_model_dir çağrıldığını doğrula
    sm.get_resolved_model_dir.assert_called_once()
    
    # WhisperModel'in çözülen dizinle başlatıldığını doğrula
    mock_fw.WhisperModel.assert_called()
    args, kwargs = mock_fw.WhisperModel.call_args
    assert args[0] == str(tmp_path)


