import time
from PySide6.QtCore import Signal
from workers.base_worker import BaseWorker


class HotkeyWorker(BaseWorker):
    hotkey_pressed  = Signal()
    hotkey_released = Signal()

    def __init__(self, settings, key: str = "F9", parent=None):
        super().__init__(parent)
        self.settings = settings
        self._key         = key.lower()
        self._is_key_down = False
        self._running     = False
        self._paused      = False

    # ------------------------------------------------------------------ QThread
    def run(self):
        import keyboard
        self._running = True
        try:
            while self._running:
                try:
                    currently_down = keyboard.is_pressed(self._key)
                except Exception:
                    self.log_entry.emit("ERR", "KEY", "Keyboard read error")
                    self.error_occurred.emit("Keyboard read error")
                    time.sleep(1.0)
                    continue

                if self._paused:
                    self._is_key_down = False  # clear state while paused
                    time.sleep(0.05)
                    continue

                if currently_down and not self._is_key_down:
                    self._is_key_down = True
                    self.hotkey_pressed.emit()

                elif not currently_down and self._is_key_down:
                    self._is_key_down = False
                    self.hotkey_released.emit()

                time.sleep(0.05)  # 50 ms polling — CPU-friendly

        except Exception:
            self.log_entry.emit("ERR", "KEY", "Hotkey crashed")
            self.error_occurred.emit("Hotkey not working")

    def set_key(self, key: str):
        self._key         = key.lower()
        self._is_key_down = False  # clear any half-finished state

    def pause(self) -> None:
        """Temporarily disables the hotkey, e.g. during hotkey-capture mode."""
        self._paused = True
        self._is_key_down = False

    def resume(self) -> None:
        """Re-enables hotkey listening.

        If the key is still physically held, _is_key_down is set to True so
        the worker enters 'already held' mode. The next hotkey_pressed fires
        only after the key is released and pressed again — no magic timer needed.
        """
        import keyboard
        self._is_key_down = keyboard.is_pressed(self._key)
        self._paused = False

    def stop(self) -> None:
        self._running = False
