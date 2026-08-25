import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from core.settings import WHISPER_MODELS

@dataclass
class LocalModel:
    repo_id: str
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
            repo_id = info["repo_id"]
            folder_name = repo_id.split('/')[-1]
            expected_path = self.base_download_dir / folder_name
            
            is_installed = self._is_valid_model_dir(expected_path)
            
            path_str = str(expected_path.resolve()) if is_installed else None
            is_active = self.active_model_path == path_str if path_str else False
            
            name = f"{key.capitalize()} ({info['size']}) — {info['desc']}"
            
            models.append(LocalModel(
                repo_id=repo_id,
                name=name,
                path=path_str,
                is_installed=is_installed,
                is_active=is_active
            ))
        return models

    def get_active_model_path(self) -> Optional[str]:
        if self.active_model_path and self._is_valid_model_dir(Path(self.active_model_path)):
            return self.active_model_path
        
        for model in self.get_available_models():
            if model.is_installed and model.path is not None:
                return model.path
                
        return None

    def _is_valid_model_dir(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        if (path / "config.json").exists() and (
            (path / "model.bin").exists() or (path / "model.safetensors").exists()
        ):
            return True
        return False

    def resolve_model_dir(self, path: Path | str) -> Optional[str]:
        if not path:
            return None
        p = Path(path)
        if not p.is_dir():
            return None
        if self._is_valid_model_dir(p):
            return str(p)
        try:
            for root, dirs, files in os.walk(str(p)):
                depth = len(Path(root).relative_to(p).parts)
                if depth > 4:
                    dirs.clear()
                    continue
                if "config.json" in files and ("model.bin" in files or "model.safetensors" in files):
                    return str(Path(root).resolve())
        except OSError:
            pass
        return None
