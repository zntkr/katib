import os
import pytest
from pathlib import Path
from core.models import ModelProvider, LocalModel

def test_available_models_returns_empty_when_no_models_exist(tmp_path):
    provider = ModelProvider(base_download_dir=tmp_path)
    
    models = provider.get_available_models()
    
    assert len(models) > 0
    assert all(m.is_installed == False for m in models)

def test_available_models_detects_installed_models(tmp_path):
    base_dir = tmp_path / "models"
    base_dir.mkdir()
    
    model_dir = base_dir / "faster-whisper-small"
    model_dir.mkdir()
    (model_dir / "config.json").touch()
    (model_dir / "model.bin").touch()
    
    provider = ModelProvider(base_download_dir=base_dir)
    models = provider.get_available_models()
    
    small_model = next((m for m in models if m.repo_id == "Systran/faster-whisper-small"), None)
    assert small_model is not None
    assert small_model.is_installed == True
    assert small_model.path == str(model_dir.resolve())
    
    base_model = next((m for m in models if m.repo_id == "Systran/faster-whisper-base"), None)
    assert base_model is not None
    assert base_model.is_installed == False

def test_get_active_model_path_returns_active_if_valid(tmp_path):
    base_dir = tmp_path / "models"
    base_dir.mkdir()
    model_dir = base_dir / "faster-whisper-small"
    model_dir.mkdir()
    (model_dir / "config.json").touch()
    (model_dir / "model.bin").touch()
    
    provider = ModelProvider(base_download_dir=base_dir, active_model_path=str(model_dir.resolve()))
    assert provider.get_active_model_path() == str(model_dir.resolve())

def test_get_active_model_path_falls_back_if_active_invalid(tmp_path):
    base_dir = tmp_path / "models"
    base_dir.mkdir()
    
    # invalid model folder (missing files)
    invalid_dir = base_dir / "faster-whisper-tiny"
    invalid_dir.mkdir()
    
    # valid model folder
    valid_dir = base_dir / "faster-whisper-small"
    valid_dir.mkdir()
    (valid_dir / "config.json").touch()
    (valid_dir / "model.bin").touch()
    
    # Initialize with invalid active path
    provider = ModelProvider(base_download_dir=base_dir, active_model_path=str(invalid_dir.resolve()))
    # It should fallback to the valid one
    assert provider.get_active_model_path() == str(valid_dir.resolve())

