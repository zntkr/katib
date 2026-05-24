"""
BaseWorker and measure_time decorator tests.
time.perf_counter is mocked so that timing measurements are deterministic.
"""
import pytest
from unittest.mock import patch
from PySide6.QtCore import QObject, Signal
from workers.base_worker import measure_time, BaseWorker


class DummyWorker(QObject):
    """Dummy worker class for testing the measure_time decorator."""
    log_entry = Signal(str, str, str)

    @measure_time("TST", "Sample Operation")
    def do_work(self, return_value="Success"):
        return return_value

    @measure_time("TST", "Failing Operation")
    def crash_work(self):
        raise ValueError("Simulated error")


class TestMeasureTimeDecorator:
    
    def test_emits_prf_log_with_correct_format(self, qapp):
        worker = DummyWorker()
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        
        worker.do_work()
        
        assert len(logs) == 1
        level, component, message = logs[0]
        assert level == "OK"
        assert component == "TST"
        assert "[Sample Operation] completed:" in message

    def test_measures_elapsed_time_accurately(self, qapp):
        worker = DummyWorker()
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))

        # Mock time.perf_counter() to return 1.000 and then 1.150 on successive calls
        # (simulating exactly 150 ms elapsed).
        with patch("workers.base_worker.time.perf_counter", side_effect=[1.000, 1.150]):
            worker.do_work()

        message = logs[0][2]
        # Verify that "150.0 ms" was logged
        assert "150.0 ms" in message

    def test_preserves_function_return_value(self, qapp):
        worker = DummyWorker()

        # Verify that the decorator does not swallow the function's return value
        result = worker.do_work(return_value="Expected Data")
        assert result == "Expected Data"

    def test_emits_time_even_on_exception(self, qapp):
        worker = DummyWorker()
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))

        # Test that elapsed time is logged via the finally block even when the function raises
        with patch("workers.base_worker.time.perf_counter", side_effect=[2.000, 2.050]):
            with pytest.raises(ValueError, match="Simulated error"):
                worker.crash_work()

        # Log must have been emitted even if the exception escaped try-except
        assert len(logs) == 1
        assert "50.0 ms" in logs[0]