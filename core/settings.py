import os
import json
import logging
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

APP_NAME                = "Katib"
DEFAULT_DOWNLOAD_PARENT = Path.home() / ".katib_app" / "models"

MSG_MODEL_NOT_FOUND  = "status.no_model"
MSG_MIC_UNAVAILABLE  = "status.no_mic"
STATE_PROCESSING    = "status.writing"
STATE_LISTENING     = "status.listening"
STATE_READY         = "status.ready"


WHISPER_MODELS = {
    "tiny": {
        "repo_id": "Systran/faster-whisper-tiny",
        "size": "~150 MB",
        "desc": "Very Fast, Low Accuracy (Old PCs)",
        "req_bytes": 500 * 1024**2
    },
    "base": {
        "repo_id": "Systran/faster-whisper-base",
        "size": "~300 MB",
        "desc": "Fast, Decent Accuracy",
        "req_bytes": 500 * 1024**2
    },
    "small": {
        "repo_id": "Systran/faster-whisper-small",
        "size": "~500 MB",
        "desc": "Balanced (Default / Recommended)",
        "req_bytes": 1 * 1024**3
    },
    "medium": {
        "repo_id": "Systran/faster-whisper-medium",
        "size": "~1.5 GB",
        "desc": "Slow, High Accuracy (High-End Hardware)",
        "req_bytes": 2 * 1024**3
    },
    "large-v3": {
        "repo_id": "Systran/faster-whisper-large-v3",
        "size": "~3 GB",
        "desc": "Very Slow, Maximum Accuracy (Top-End Hardware)",
        "req_bytes": 4 * 1024**3
    }
}

COMPUTE_TYPE_OPTIONS_CPU  = ("int8", "int8_float32", "float32")
COMPUTE_TYPE_OPTIONS_CUDA = ("float16", "int8_float16", "float32")

@dataclass
class SettingDef:
    key: str
    type_: type
    default: Any
    ui_group: str
    ui_label: str
    ui_widget: str  # 'spinbox', 'doublespinbox', 'combobox', 'checkbox', 'lineedit', 'custom'
    ui_kwargs: dict = field(default_factory=dict)
    tooltip: str = ""

SETTINGS_SCHEMA = [
    SettingDef("hotkey", str, "F9", "General", "settings.hotkey_label", "custom"),
    SettingDef("app_language", str, "", "General", "settings.app_language_label", "custom"),
    SettingDef("model_dir", str, "", "Model", "Model Path", "custom"),
    SettingDef("device_index", int, None, "Audio", "Microphone", "custom"),
    SettingDef("selected_model_repo", str, "", "Model", "Selected Model", "custom"),

    # Auto-generated UI settings:
    SettingDef("language", str, "auto", "Processing", "schema.language.label", "combobox",
               {"options": [("Auto Detect", "auto"), ("Arabic", "ar"), ("Chinese", "zh"), ("English", "en"), ("French", "fr"), ("German", "de"), ("Greek", "el"), ("Hindi", "hi"), ("Indonesian", "id"), ("Italian", "it"), ("Japanese", "ja"), ("Korean", "ko"), ("Persian", "fa"), ("Portuguese", "pt"), ("Russian", "ru"), ("Spanish", "es"), ("Turkish", "tr"), ("Urdu", "ur")], "full_width": True}),
    SettingDef("compute_type", str, "int8", "Processing", "schema.compute_type.label", "custom",
               {"full_width": True}, tooltip="schema.compute_type.tooltip"),

    SettingDef("initial_prompt", str, "",
               "Processing", "schema.initial_prompt.label", "lineedit",
               {"full_width": True}, "schema.initial_prompt.tooltip")
]


def get_settings_path() -> Path:
    settings_dir = Path.home() / ".katib_app"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / "settings.json"


def validate_model_dir(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_dir():
        return None

    if (p / "config.json").exists() and (
        (p / "model.bin").exists() or (p / "model.safetensors").exists()
    ):
        return str(p)

    try:
        for root, dirs, files in os.walk(str(p)):
            depth = len(Path(root).relative_to(p).parts)
            if depth > 4:
                dirs.clear()
                continue
            if "config.json" in files and (
                "model.bin" in files or "model.safetensors" in files
            ):
                return str(Path(root).resolve())
    except OSError:
        pass

    return None


def find_fallback_model_dir(parent_path: Path) -> str | None:
    """Returns the first valid model directory found under the given parent."""
    if not parent_path.exists() or not parent_path.is_dir():
        return None

    try:
        # Check parent_path itself first (model may have been placed directly there).
        res = validate_model_dir(str(parent_path))
        if res:
            return res

        # Walk immediate subdirectories.
        for item in parent_path.iterdir():
            if item.is_dir():
                res = validate_model_dir(str(item))
                if res:
                    return res
    except OSError:
        pass
        
    return None


class SettingsManager:
    """Dependency Injected Settings Repository & Validator"""
    
    def __init__(self, in_memory: bool = False):
        self.in_memory = in_memory
        self._cache: dict[str, Any] = {}
        
        # Populate defaults from schema
        for s in SETTINGS_SCHEMA:
            self._cache[s.key] = s.default
            
        if not self.in_memory:
            self._load()
            
    def _load(self):
        path = get_settings_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                parsed = json.load(f)
                if isinstance(parsed, dict):
                    self._cache.update(parsed)
        except json.JSONDecodeError as e:
            logger.warning("Settings file corrupted, using defaults: %s", e)
        except OSError as e:
            logger.error("Settings file could not be read: %s", e)
            
    def save(self):
        if self.in_memory:
            return
        path = get_settings_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=4)
        except OSError as e:
            logger.error("Settings could not be saved: %s", e)
            
    def get(self, key: str, default: Any = None) -> Any:
        schema_default = next((s.default for s in SETTINGS_SCHEMA if s.key == key), default)
        val = self._cache.get(key, schema_default)

        if key == "language" and val == "auto":
            return None
        if key == "compute_type":
            valid = COMPUTE_TYPE_OPTIONS_CPU
            return val if val in valid else "int8"

        return val

    def get_resolved_model_dir(self) -> str | None:
        """Validates the saved model dir; falls back to scanning if invalid."""
        current = self.get("model_dir")
        validated = validate_model_dir(current)
        if validated:
            return validated

        # Fallback: scan the default download location.
        fallback = find_fallback_model_dir(DEFAULT_DOWNLOAD_PARENT)
        if fallback:
            self.set("model_dir", fallback)
            return fallback
            
        return None

    def set(self, key: str, value: Any, _save: bool = True):
        if key == "language" and value is None:
            self._cache[key] = "auto"
        else:
            self._cache[key] = value
        if _save:
            self.save()

    def set_many(self, mapping: dict) -> None:
        """Saves multiple settings atomically with a single JSON write."""
        if not mapping:
            return
        for key, value in mapping.items():
            self.set(key, value, _save=False)
        self.save()

    def reset_processing_settings(self):
        for s in SETTINGS_SCHEMA:
            if s.ui_group == "Processing":
                self._cache[s.key] = s.default
        self.save()
