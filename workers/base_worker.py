import time
from functools import wraps
from abc import abstractmethod
from PySide6.QtCore import QThread, Signal

def measure_time(component: str, task_name: str):
    """Worker metotlarının çalışma süresini milisaniye hassasiyetinde ölçüp loglayan dekoratör."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.perf_counter()
            try:
                return func(self, *args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                # BaseWorker'dan türeyen sınıflarda log_entry sinyali daima bulunur.
                if hasattr(self, 'log_entry'):
                    self.log_entry.emit("OK", component, f"[{task_name}] tamamlandı: {elapsed_ms:.1f} ms")
        return wrapper
    return decorator

class BaseWorker(QThread):
    """Tüm worker'ların paylaştığı sinyal sözleşmesi ve ortak arayüz."""

    log_entry      = Signal(str, str, str)  # level, component, message
    error_occurred = Signal(str)

    @abstractmethod
    def stop(self) -> None: ...
