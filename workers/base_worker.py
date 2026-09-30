import time
from functools import wraps
from abc import abstractmethod
from PySide6.QtCore import QThread, Signal

from core.log import get_logger, OK

def measure_time(component: str, task_name: str):
    """Decorator that measures worker method execution time in milliseconds and logs the result."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.perf_counter()
            try:
                return func(self, *args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                get_logger(component).log(OK, f"[{task_name}] completed: {elapsed_ms:.1f} ms")
        return wrapper
    return decorator

class BaseWorker(QThread):
    """Shared signal contract and common interface for all workers."""

    error_occurred = Signal(str)

    @abstractmethod
    def stop(self) -> None: ...
