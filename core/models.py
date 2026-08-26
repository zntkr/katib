import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from core.settings import WHISPER_MODELS

@dataclass
class LocalModel:
    repo_id: str  # We will use the key (e.g., 'small', 'medium') here
    name: str
    path: Optional[str]
    is_installed: bool
    is_active: bool

class ModelProvider:
    def __init__(self, base_download_dir: Path | str, active_model_path: str = None):
        self.base_download_dir = Path(base_download_dir)
        self.active_model_path = active_model_path

    def get_available_models(self) -> List[LocalModel]:
        models = []
        for key, info in WHISPER_MODELS.items():
            expected_path = self.base_download_dir / info["filename"]
            
            is_installed = expected_path.is_file()
            
            path_str = str(expected_path.resolve()) if is_installed else None
            is_active = self.active_model_path == path_str if path_str else False
            
            name = f"{key.capitalize()} ({info['size']}) — {info['desc']}"
            
            models.append(LocalModel(
                repo_id=key,  # Use 'key' as the unique identifier
                name=name,
                path=path_str,
                is_installed=is_installed,
                is_active=is_active
            ))
        return models

    def get_active_model_path(self) -> Optional[str]:
        if self.active_model_path and Path(self.active_model_path).is_file():
            return self.active_model_path
        
        for model in self.get_available_models():
            if model.is_installed and model.path is not None:
                return model.path
                
        return None

    def resolve_model_dir(self, path: Path | str) -> Optional[str]:
        # Note: path is now a path to a .bin file
        if not path:
            return None
        p = Path(path)
        if p.is_file() and p.suffix in ('.bin', '.gguf'):
            return str(p.resolve())
        return None
