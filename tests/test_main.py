"""
main.py — testable parts:
  - StreamToLogger
  - setup_logging() (log directory, fallback, stdout/stderr binding, sys.excepthook)
  - handle_exception (excepthook body)
"""
import logging
import sys
from unittest.mock import MagicMock, patch


# ────────────────────────────────────────── StreamToLogger ──────────────────

class TestStreamToLogger:
    def _make(self, level=logging.INFO):
        from main import StreamToLogger
        logger = MagicMock()
        stream = StreamToLogger(logger, level)
        return stream, logger

    def test_write_single_line(self):
        stream, logger = self._make()
        stream.write("hello world\n")
        logger.log.assert_called_once_with(logging.INFO, "hello world")

    def test_write_multiple_lines(self):
        stream, logger = self._make()
        stream.write("line1\nline2\n")
        assert logger.log.call_count == 2

    def test_write_empty_line_skipped(self):
        """Lines that contain only whitespace must not be logged."""
        stream, logger = self._make()
        stream.write("   \n")
        logger.log.assert_not_called()

    def test_write_returns_buf_length(self):
        stream, logger = self._make()
        buf = "test\n"
        assert stream.write(buf) == len(buf)

    def test_write_uses_given_level(self):
        stream, logger = self._make(level=logging.ERROR)
        stream.write("err\n")
        logger.log.assert_called_once_with(logging.ERROR, "err")

    def test_flush_is_noop(self):
        stream, _ = self._make()
        stream.flush()  # must not raise


# ────────────────────────────────────────── setup_logging ───────────────────

class TestSetupLogging:
    def test_returns_logger(self, tmp_path):
        with patch("main.Path.home", return_value=tmp_path), \
             patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
            from main import setup_logging
            logger = setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_creates_log_directory(self, tmp_path):
        log_base = tmp_path / "AppData" / "Local"
        with patch.dict("os.environ", {"LOCALAPPDATA": str(log_base)}):
            from main import setup_logging
            setup_logging()
        assert (log_base / "Katib" / "Logs").is_dir()

    def test_fallback_on_mkdir_error(self, tmp_path):
        """If directory creation fails, the fallback basicConfig must run."""
        with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}), \
             patch("main.Path.mkdir", side_effect=PermissionError("access denied")):
            from main import setup_logging
            logger = setup_logging()  # must not crash
        assert isinstance(logger, logging.Logger)

    def test_localappdata_missing_uses_home(self, tmp_path):
        env = {k: v for k, v in __import__("os").environ.items() if k != "LOCALAPPDATA"}
        with patch.dict("os.environ", env, clear=True), \
             patch("main.Path.home", return_value=tmp_path):
            from main import setup_logging
            logger = setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_stdout_none_replaced(self, tmp_path):
        original_stdout = sys.stdout
        sys.stdout = None  # type: ignore
        try:
            with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
                from main import setup_logging
                setup_logging()
            assert sys.stdout is not None
        finally:
            sys.stdout = original_stdout

    def test_stderr_none_replaced(self, tmp_path):
        original_stderr = sys.stderr
        sys.stderr = None  # type: ignore
        try:
            with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
                from main import setup_logging
                setup_logging()
            assert sys.stderr is not None
        finally:
            sys.stderr = original_stderr

    def test_excepthook_installed(self, tmp_path):
        with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
            from main import setup_logging
            setup_logging()
        assert sys.excepthook is not sys.__excepthook__


# ────────────────────────────────── handle_exception (excepthook) ───────────

class TestHandleException:
    """Behaviours of handle_exception installed as sys.excepthook."""

    def _get_hook(self, tmp_path):
        with patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}):
            from main import setup_logging
            setup_logging()
        return sys.excepthook

    def test_keyboard_interrupt_calls_default_hook(self, tmp_path):
        hook = self._get_hook(tmp_path)
        with patch("sys.__excepthook__") as mock_default:
            hook(KeyboardInterrupt, KeyboardInterrupt(), None)
        mock_default.assert_called_once()

    def test_normal_exception_logs_error(self, tmp_path):
        hook = self._get_hook(tmp_path)
        logger = logging.getLogger("Katib")
        with patch.object(logger, "error") as mock_err:
            try:
                raise ValueError("test error")
            except ValueError as exc:
                hook(type(exc), exc, exc.__traceback__)
        mock_err.assert_called_once()
        logged = mock_err.call_args[0][0]
        assert "test error" in logged

    def test_exception_log_contains_locals(self, tmp_path):
        hook = self._get_hook(tmp_path)
        logger = logging.getLogger("Katib")
        with patch.object(logger, "error") as mock_err:
            try:
                my_local_var = "sentinel_value"  # noqa: F841
                raise RuntimeError("locals test")
            except RuntimeError as exc:
                hook(type(exc), exc, exc.__traceback__)
        logged = mock_err.call_args[0][0]
        assert "LOCALS" in logged or "sentinel_value" in logged

    def test_locals_pformat_error_handled(self, tmp_path):
        """handle_exception must not crash when pprint.pformat raises."""
        hook = self._get_hook(tmp_path)
        with patch("main.pprint.pformat", side_effect=Exception("format error")):
            try:
                raise RuntimeError("test")
            except RuntimeError as exc:
                hook(type(exc), exc, exc.__traceback__)   # must not crash

    def test_locals_truncated_when_too_long(self, tmp_path):
        """Content must be truncated when locals_str > 4096 (line 94)."""
        hook = self._get_hook(tmp_path)
        logger = logging.getLogger("Katib")
        big_str = "x" * 5000
        with patch("main.pprint.pformat", return_value=big_str), \
             patch.object(logger, "error") as mock_err:
            try:
                raise RuntimeError("big locals")
            except RuntimeError as exc:
                hook(type(exc), exc, exc.__traceback__)
        logged = mock_err.call_args[0][0]
        assert "truncated" in logged
