import os
import sys
import json
import logging
from pathlib import Path
from typing import Any

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


# "bytes" is what a download fetches: the sum of every file in the repository, read from
# huggingface.co on 2026-10-10. The model list, the download progress and the user guide
# show it through format_size().
WHISPER_MODELS = {
    "tiny": {
        "repo_id": "Systran/faster-whisper-tiny",
        "bytes": 78_207_087,
        "desc": "Very Fast, Low Accuracy (Old PCs)",
        "req_bytes": 500 * 1024**2
    },
    "base": {
        "repo_id": "Systran/faster-whisper-base",
        "bytes": 147_886_409,
        "desc": "Fast, Decent Accuracy",
        "req_bytes": 500 * 1024**2
    },
    "small": {
        "repo_id": "Systran/faster-whisper-small",
        "bytes": 486_215_847,
        "desc": "Balanced (Default / Recommended)",
        "req_bytes": 1 * 1024**3
    },
    "medium": {
        "repo_id": "Systran/faster-whisper-medium",
        "bytes": 1_530_575_217,
        "desc": "Slow, High Accuracy (High-End Hardware)",
        "req_bytes": 2 * 1024**3
    },
    "large-v3": {
        "repo_id": "Systran/faster-whisper-large-v3",
        "bytes": 3_090_839_273,
        "desc": "Very Slow, Maximum Accuracy (Top-End Hardware)",
        "req_bytes": 4 * 1024**3
    }
}

def format_size(n_bytes: float) -> str:
    """"78 MB", "1.5 GB". Decimal units, as the download site shows them."""
    return f"{n_bytes / 1e9:.1f} GB" if n_bytes >= 1e9 else f"{n_bytes / 1e6:.0f} MB"


COMPUTE_TYPE_OPTIONS_CPU  = ("int8", "int8_float32", "float32")
COMPUTE_TYPE_OPTIONS_CUDA = ("float16", "int8_float16", "float32")
COMPUTE_DEVICE_OPTIONS    = ("auto", "cpu", "cuda")  # auto: GPU when usable, else CPU (ADR-0010)

# Choices the settings window offers: (label, stored value).
INJECTION_METHODS = (("Clipboard (Fast)", "clipboard"), ("Keystroke (Safe)", "keystroke"))
SPEECH_LANGUAGES = (
    ("Auto Detect", "auto"), ("Arabic", "ar"), ("Chinese", "zh"), ("English", "en"), ("French", "fr"),
    ("German", "de"), ("Greek", "el"), ("Hindi", "hi"), ("Indonesian", "id"), ("Italian", "it"),
    ("Japanese", "ja"), ("Korean", "ko"), ("Persian", "fa"), ("Portuguese", "pt"), ("Russian", "ru"),
    ("Spanish", "es"), ("Turkish", "tr"), ("Urdu", "ur"),
)

# Every setting and its default: the single list of what settings.json may hold.
# Nothing here describes the UI; the settings window builds its widgets by hand (ADR-0012).
DEFAULTS: dict[str, Any] = {
    "hotkey": "F9",
    "app_language": "",
    "injection_method": "clipboard",
    "device_index": None,
    "device_name": "",
    "model_dir": str(DEFAULT_DOWNLOAD_PARENT),
    # No longer read or written (2026-10-10): the model list shows the model in use, not a
    # remembered pick. Kept because removing a key needs the owner's approval (CONTEXT.md rule 8).
    "selected_model_repo": "Systran/faster-whisper-small",
    "language": "auto",
    "compute_type": "int8",
    "compute_device": "auto",
    "initial_prompt": "",
    "initial_prompts": None,  # {speech language: prompt}, filled as the user saves prompts
}


# The prompt a speech language starts with until the user saves their own: one ordinary,
# well-punctuated sentence nudges Whisper towards punctuation and capitals.
DEFAULT_PROMPTS: dict[str, str] = {
    "ar": "مرحباً. أقوم اليوم بتدوين ملاحظاتي بالصوت.",
    "de": "Hallo. Ich diktiere heute meine Notizen per Sprache.",
    "el": "Γεια σας. Σήμερα υπαγορεύω τις σημειώσεις μου φωνητικά.",
    "en": "Hello. I'm dictating my notes using voice today.",
    "es": "Hola. Hoy estoy dictando mis notas por voz.",
    "fa": "سلام. امروز یادداشت‌های خود را به صورت صوتی دیکته می‌کنم.",
    "fr": "Bonjour. Je dicte mes notes à voix haute aujourd'hui.",
    "hi": "नमस्ते। आज मैं अपने नोट्स आवाज़ से बोल रहा हूँ।",
    "id": "Halo. Hari ini saya mendiktekan catatan saya secara lisan.",
    "it": "Ciao. Oggi sto dettando le mie note a voce.",
    "ja": "こんにちは。今日は音声でメモを書き取っています。",
    "ko": "안녕하세요. 오늘 음성으로 메모를 받아쓰고 있습니다.",
    "pt": "Olá. Hoje estou ditando minhas anotações por voz.",
    "ru": "Привет. Сегодня я диктую свои заметки голосом.",
    "tr": "Merhaba. Bugün notlarımı sesli olarak dikte ediyorum.",
    "ur": "السلام علیکم۔ آج میں اپنے نوٹس آواز سے لکھوا رہا ہوں۔",
    "zh": "你好。今天我正在用语音记录我的笔记。",
}


def first_run_speech_settings(system_code: str) -> dict[str, str]:
    """The speech language a new install starts with, and its stock prompt, as if the user
    had picked it in the settings window: the computer's language when Katib lists it, else
    automatic detection (no prompt). A fixed language skips detection, which costs an extra
    encoder pass and can pick the wrong language on a short clip (plan 0012 Faz 5).
    An unlisted language falls back to detection, not English: forcing English on someone
    speaking Dutch would garble the text, detection still writes Dutch."""
    listed = {code for _, code in SPEECH_LANGUAGES if code != "auto"}
    language = system_code if system_code in listed else "auto"
    return {"language": language, "initial_prompt": DEFAULT_PROMPTS.get(language, "")}


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
        self._cache: dict[str, Any] = dict(DEFAULTS)
        # No settings.json yet: a new install. Existing users keep what they have (CONTEXT.md #8).
        self.first_run = False

        if not self.in_memory:
            self._load()
            
    def _load(self):
        path = get_settings_path()
        if not path.exists():
            self.first_run = True
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
        # Only values that differ from the default are written, so a default
        # changed in a later version still reaches existing users.
        data = {k: v for k, v in self._cache.items() if k not in DEFAULTS or v != DEFAULTS[k]}
        path = get_settings_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except OSError as e:
            logger.error("Settings could not be saved: %s", e)
            
    def get(self, key: str, default: Any = None) -> Any:
        val = self._cache.get(key, DEFAULTS.get(key, default))

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
