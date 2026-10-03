import os
import sys
import json
import logging
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

APP_NAME = "Katib"


def get_app_data_dir() -> Path:
    """Single root for all Katib data: settings.json, Models/ and Logs/ (ADR-0009)."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        base_dir = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    return base_dir / APP_NAME


def get_log_dir() -> Path:
    return get_app_data_dir() / "Logs"


DEFAULT_DOWNLOAD_PARENT = get_app_data_dir() / "Models"
LEGACY_DATA_DIR         = Path.home() / ".katib_app"  # used by builds before ADR-0009

MSG_MODEL_NOT_FOUND  = "status.no_model"
MSG_MIC_UNAVAILABLE  = "status.no_mic"
STATE_PROCESSING    = "status.writing"
STATE_LISTENING     = "status.listening"
STATE_READY         = "status.ready"
STATE_LOADING       = "status.loading_model"


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
COMPUTE_DEVICE_OPTIONS    = ("auto", "cpu", "cuda")  # auto: GPU when usable, else CPU (ADR-0010)

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
    SettingDef("theme", str, "system", "General", "settings.theme_label", "custom"),
    SettingDef("model_dir", str, str(DEFAULT_DOWNLOAD_PARENT), "Model", "Model Path", "custom"),
    SettingDef("device_index", int, None, "Audio", "Microphone", "custom"),
    SettingDef("selected_model_repo", str, "Systran/faster-whisper-small", "Model", "Selected Model", "custom"),
    SettingDef("injection_method", str, "clipboard", "General", "settings.injection_method_label", "combobox",
               {"options": [("Clipboard (Fast)", "clipboard"), ("Keystroke (Safe)", "keystroke")], "full_width": True}),

    # Auto-generated UI settings:
    SettingDef("language", str, "auto", "Processing", "schema.language.label", "combobox",
               {"options": [("Auto Detect", "auto"), ("Arabic", "ar"), ("Chinese", "zh"), ("English", "en"), ("French", "fr"), ("German", "de"), ("Greek", "el"), ("Hindi", "hi"), ("Indonesian", "id"), ("Italian", "it"), ("Japanese", "ja"), ("Korean", "ko"), ("Persian", "fa"), ("Portuguese", "pt"), ("Russian", "ru"), ("Spanish", "es"), ("Turkish", "tr"), ("Urdu", "ur")], "full_width": True}),
    SettingDef("compute_type", str, "int8", "Processing", "schema.compute_type.label", "custom",
               {"full_width": True}, tooltip="schema.compute_type.tooltip"),
    SettingDef("compute_device", str, "auto", "Processing", "Compute Device", "custom"),

    SettingDef("initial_prompt", str, "",
               "Processing", "schema.initial_prompt.label", "lineedit",
               {"full_width": True}, "schema.initial_prompt.tooltip")
]


def get_settings_path() -> Path:
    settings_dir = get_app_data_dir()
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / "settings.json"


def migrate_legacy_data(legacy_dir: Path | None = None, app_dir: Path | None = None) -> None:
    """Moves settings and models written by builds before ADR-0009 from ~/.katib_app
    into the app data dir. Runs on every startup; a no-op once nothing is left to move.

    Never raises: on any failure the legacy data stays where it is and keeps working.
    """
    legacy_dir = legacy_dir or LEGACY_DATA_DIR
    app_dir = app_dir or get_app_data_dir()
    if not legacy_dir.is_dir():
        return
    try:
        logger.info("Migrating legacy data: %s -> %s", legacy_dir, app_dir)
        app_dir.mkdir(parents=True, exist_ok=True)
        legacy_models, new_models = legacy_dir / "models", app_dir / "Models"
        _move_legacy_models(legacy_models, new_models)
        _move_legacy_settings(legacy_dir / "settings.json", app_dir / "settings.json",
                              legacy_models, new_models)
        legacy_dir.rmdir()  # only succeeds once everything has been moved
    except OSError as e:
        logger.warning("Legacy data migration incomplete, leftovers stay in %s: %s", legacy_dir, e)
    except Exception:
        logger.exception("Legacy data migration failed")


def _move_legacy_models(legacy_models: Path, new_models: Path) -> None:
    if not legacy_models.is_dir():
        return
    new_models.mkdir(parents=True, exist_ok=True)
    for child in legacy_models.iterdir():
        target = new_models / child.name
        if target.exists():
            logger.info("Keeping %s, already present in %s", child.name, new_models)
            continue
        try:
            os.rename(child, target)  # same profile volume: instant, even for GBs
        except OSError as e:
            logger.warning("Could not move %s: %s", child, e)
    try:
        legacy_models.rmdir()
    except OSError:
        pass


def _move_legacy_settings(legacy_settings: Path, new_settings: Path,
                          legacy_models: Path, new_models: Path) -> None:
    if not legacy_settings.is_file() or new_settings.exists():
        return
    try:
        data = json.loads(legacy_settings.read_text(encoding="utf-8"))
    except ValueError:
        data = None
    if not isinstance(data, dict):
        os.replace(legacy_settings, new_settings)  # SettingsManager falls back to defaults
        return
    if data.get("model_dir"):
        data["model_dir"] = _migrate_model_dir(data["model_dir"], legacy_models, new_models)
    new_settings.write_text(json.dumps(data, indent=4), encoding="utf-8")
    legacy_settings.unlink()


def _migrate_model_dir(model_dir: str, legacy_models: Path, new_models: Path) -> str:
    path = Path(model_dir)
    if not path.is_relative_to(legacy_models):
        return model_dir  # user picked a folder elsewhere
    if path != legacy_models:
        # A specific model: follow it if it moved, otherwise keep using it in place.
        return model_dir if path.exists() else str(new_models / path.relative_to(legacy_models))

    # The old default (the models root itself). ModelProvider only scans the new
    # root, so name a concrete model if the new root has none but one was left behind.
    from core.models import ModelProvider
    if ModelProvider(new_models).get_active_model_path() is None:
        left_behind = ModelProvider(legacy_models).resolve_model_dir(legacy_models)
        if left_behind:
            return left_behind
    return str(new_models)


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
        # Only values that differ from the schema default are written, so a default
        # changed in a later version still reaches existing users.
        defaults = {s.key: s.default for s in SETTINGS_SCHEMA}
        data = {k: v for k, v in self._cache.items() if k not in defaults or v != defaults[k]}
        path = get_settings_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
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
        if key == "compute_device":
            return val if val in COMPUTE_DEVICE_OPTIONS else "auto"

        return val

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
