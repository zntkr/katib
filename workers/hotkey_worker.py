import sys
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

    def _is_pressed(self, key: str) -> bool:
        if sys.platform == "win32":
            import keyboard
            return keyboard.is_pressed(key)
        else:
            from pynput import keyboard as pynput_kb
            # pynput doesn't expose a synchronous is_pressed; we rely on the
            # listener state tracked in run() via on_press/on_release instead.
            return self._is_key_down_pynput

    # ------------------------------------------------------------------ QThread
    def run(self):
        self._running = True
        if sys.platform == "win32":
            self._run_windows()
        else:
            self._run_linux()

    def _run_windows(self):
        import keyboard
        try:
            while self._running:
                try:
                    currently_down = keyboard.is_pressed(self._key)
                except Exception:
                    self.log_entry.emit("ERR", "KEY", "Keyboard read error")
                    self.error_occurred.emit("osd.keyboard_error")
                    time.sleep(1.0)
                    continue

                if self._paused:
                    self._is_key_down = False
                    time.sleep(0.05)
                    continue

                if currently_down and not self._is_key_down:
                    self._is_key_down = True
                    self.hotkey_pressed.emit()
                elif not currently_down and self._is_key_down:
                    self._is_key_down = False
                    self.hotkey_released.emit()

                time.sleep(0.05)
        except Exception:
            self.log_entry.emit("ERR", "KEY", "Hotkey crashed")
            self.error_occurred.emit("osd.hotkey_failed")

    def _run_linux(self):
        from pynput import keyboard as pynput_kb

        self._is_key_down_pynput = False

        def _canonical_key(key):
            try:
                return key.char.lower() if hasattr(key, "char") and key.char else str(key).lower()
            except Exception:
                return str(key).lower()

        def on_press(key) -> None:
            k = _canonical_key(key)
            if k == self._key and not self._paused and not self._is_key_down:
                self._is_key_down = True
                self._is_key_down_pynput = True
                self.hotkey_pressed.emit()

        def on_release(key) -> None:
            k = _canonical_key(key)
            if k == self._key and not self._paused and self._is_key_down:
                self._is_key_down = False
                self._is_key_down_pynput = False
                self.hotkey_released.emit()

        try:
            listener = pynput_kb.Listener(on_press=on_press, on_release=on_release)
            listener.start()
            while self._running:
                time.sleep(0.1)
            listener.stop()
        except Exception:
            self.log_entry.emit("ERR", "KEY", "Hotkey crashed")
            self.error_occurred.emit("osd.hotkey_failed")

    def set_key(self, key: str):
        self._key         = key.lower()
        self._is_key_down = False

    def pause(self) -> None:
        self._paused = True
        self._is_key_down = False

    def resume(self) -> None:
        if sys.platform == "win32":
            import keyboard
            self._is_key_down = keyboard.is_pressed(self._key)
        else:
            self._is_key_down = False
        self._paused = False

    def stop(self) -> None:
        self._running = False
