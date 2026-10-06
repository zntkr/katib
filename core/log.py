"""
Katib logging (ADR-0004). Every component logs through the standard `logging`
module under the "Katib.<COMPONENT>" logger; main.py installs the handlers that
write the log file and feed the log tab of the settings window.

Dictated text is private: pass it as `extra={"transcript": text}` and the
message stays text-free. The log tab shows the text; files only get its length.
"""
import logging

from PySide6.QtCore import QObject, Signal

ROOT = "Katib"

OK = 25  # between INFO and WARNING: a step that completed successfully
logging.addLevelName(OK, "OK")

logging.getLogger(ROOT).setLevel(logging.INFO)  # independent of how the root logger is configured


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(f"{ROOT}.{component}")


def component_of(record: logging.LogRecord) -> str | None:
    """"MIC" for "Katib.MIC"; None for the app logger itself and third-party libraries."""
    prefix = ROOT + "."
    return record.name[len(prefix):] if record.name.startswith(prefix) else None


class PrivacyFormatter(logging.Formatter):
    """Formatter for anything written to disk or a console: transcripts become their length."""

    def format(self, record: logging.LogRecord) -> str:
        text = getattr(record, "transcript", None)
        if text is None:
            return super().format(record)
        redacted = logging.makeLogRecord(record.__dict__)  # never mutate a record other handlers share
        redacted.msg = f"{record.getMessage()} ({len(text)} chars)"
        redacted.args = None
        return super().format(redacted)


class _MaskedStr:
    def __init__(self, length: int) -> None:
        self.length = length

    def __repr__(self) -> str:
        return f"<str len={self.length}>"


def mask_text(value, depth: int = 3):
    """Replaces every string (also inside dicts/lists/tuples/sets) with its length, for crash
    dumps that are written to disk. Other objects keep their repr."""
    if isinstance(value, str):
        return _MaskedStr(len(value))
    if depth <= 0:
        return value
    if isinstance(value, dict):
        return {k: mask_text(v, depth - 1) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(mask_text(v, depth - 1) for v in value)  # plain tuple: namedtuples need named args
    if isinstance(value, (list, set, frozenset)):
        return [mask_text(v, depth - 1) for v in value]
    return value


def _log_tag(levelno: int) -> str:
    if levelno >= logging.ERROR:
        return "ERR"
    if levelno >= logging.WARNING:
        return "WRN"
    if levelno >= OK:
        return "OK"
    return "..."  # INFO: a step in progress


class _Bridge(QObject):
    entry = Signal(str, str, str)  # level tag, component, message


class LogViewHandler(logging.Handler):
    """Forwards component records ("Katib.<COMPONENT>") to the log tab of the settings window.

    Records may come from any thread (workers, PortAudio callbacks); the Qt signal
    queues them onto the window's thread. Connect `bridge.entry` in main.py.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.bridge = _Bridge()

    def emit(self, record: logging.LogRecord) -> None:
        component = component_of(record)
        if component is None:
            return
        try:
            message = record.getMessage()
            text = getattr(record, "transcript", None)
            if text is not None:
                message = f"{message}: {text!r}"
            self.bridge.entry.emit(_log_tag(record.levelno), component, message)
        except Exception:
            self.handleError(record)
