"""
ADR-0004: one logging path for every component. Seams under test:
  - the log file written by main.setup_logging()
  - DashboardLogHandler, which feeds the dashboard log box
"""
import logging
from unittest.mock import patch
import pytest

from core.log import get_logger, OK


@pytest.fixture
def log_file(tmp_path):
    """Runs the real setup_logging() against a temporary log dir and returns the file path."""
    log_dir = tmp_path / "Logs"
    with patch("main.get_log_dir", return_value=log_dir):
        from main import setup_logging
        setup_logging()
    yield log_dir / "katib.log"
    from main import setup_logging  # detach and close the temporary file handler
    with patch("main.get_log_dir", return_value=tmp_path / "Logs2"):
        setup_logging()


def _read(path):
    for h in logging.getLogger().handlers:
        h.flush()
    return path.read_text(encoding="utf-8")


class TestLogFile:
    def test_component_messages_reach_the_file(self, log_file):
        get_logger("MIC").warning("Recording is empty")
        text = _read(log_file)
        assert "Recording is empty" in text
        assert "Katib.MIC" in text

    def test_transcript_text_never_reaches_the_file(self, log_file):
        get_logger("STT").log(OK, "Transcript", extra={"transcript": "gizli toplantı notu"})
        text = _read(log_file)
        assert "gizli toplantı notu" not in text
        assert "Transcript (19 chars)" in text

    def test_setup_twice_does_not_duplicate_lines(self, log_file):
        from main import setup_logging
        with patch("main.get_log_dir", return_value=log_file.parent):
            setup_logging()
        get_logger("APP").info("only once")
        assert _read(log_file).count("only once") == 1


class TestDashboardLogHandler:
    @pytest.fixture
    def entries(self, qapp):
        from core.log import DashboardLogHandler
        handler = DashboardLogHandler()
        received = []
        handler.bridge.entry.connect(lambda lvl, comp, msg: received.append((lvl, comp, msg)))
        logging.getLogger("Katib").addHandler(handler)
        yield received
        logging.getLogger("Katib").removeHandler(handler)

    @pytest.mark.parametrize("level, shown_as", [
        (logging.INFO, "..."), (OK, "OK"), (logging.WARNING, "WRN"), (logging.ERROR, "ERR"),
    ])
    def test_component_record_is_forwarded(self, entries, level, shown_as):
        get_logger("MIC").log(level, "Device → %s", "USB Mic")
        assert entries == [(shown_as, "MIC", "Device → USB Mic")]

    def test_dashboard_shows_the_transcript_text(self, entries):
        get_logger("STT").log(OK, "Transcript", extra={"transcript": "merhaba dünya"})
        assert entries == [("OK", "STT", "Transcript: 'merhaba dünya'")]

    def test_app_logger_and_libraries_stay_out_of_the_dashboard(self, entries):
        logging.getLogger("Katib").info("=== Katib Starting ===")
        logging.getLogger("faster_whisper").warning("library noise")
        assert entries == []

    def test_debug_records_are_not_shown(self, entries):
        get_logger("MIC").debug("chatty")
        assert entries == []
