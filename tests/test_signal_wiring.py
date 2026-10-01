"""
Guards against silent disconnects (CONTEXT.md): every public signal a worker
declares must be connected in main.py, the single wiring hub (ADR-0003).
"""
from pathlib import Path
import pytest
from PySide6.QtCore import Signal

from workers.audio_worker import AudioWorker
from workers.hotkey_worker import HotkeyWorker
from workers.transcription_worker import TranscriptionWorker
from workers.model_downloader_worker import ModelDownloaderWorker

MAIN_SOURCE = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
WORKERS = {
    "audio_worker": AudioWorker,
    "hotkey_worker": HotkeyWorker,
    "transcription_worker": TranscriptionWorker,
    "downloader_worker": ModelDownloaderWorker,
}


def _public_signals(cls) -> list[str]:
    names = set()
    for klass in cls.__mro__:
        if not klass.__module__.startswith("workers."):
            continue  # skip Qt's own QThread/QObject signals
        names.update(n for n, v in vars(klass).items() if isinstance(v, Signal) and not n.startswith("_"))
    return sorted(names)


@pytest.mark.parametrize("var, signal", [
    (var, sig) for var, cls in WORKERS.items() for sig in _public_signals(cls)
])
def test_worker_signal_is_wired_in_main(var, signal):
    assert f"{var}.{signal}.connect(" in MAIN_SOURCE, (
        f"{var}.{signal} is emitted but never connected in main.py; "
        "wire it or delete the signal"
    )


@pytest.mark.parametrize("path", ["main.py", "ui/tray_app.py"])
def test_no_access_to_dashboard_internals(path):
    """main.py and TrayApp talk to the dashboard only through its public methods."""
    import re
    source = (Path(__file__).resolve().parent.parent / path).read_text(encoding="utf-8")
    hits = re.findall(r"dashboard\._\w+", source)
    assert hits == [], f"{path} reaches into dashboard internals: {sorted(set(hits))}"


def test_only_tray_app_writes_the_status_line():
    """Worker status signals go through TrayApp's priority rule, never straight to the dashboard."""
    assert "dashboard.set_status" not in MAIN_SOURCE
