import sys
import time
from PySide6.QtCore import Signal
from workers.base_worker import BaseWorker
from core.log import get_logger


_log = get_logger("KEY")

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
        self._hooks: list = []          # keyboard hook handles (Windows)
        self._modifiers: list[str] = []

    # ------------------------------------------------------------------ QThread
    def run(self):
        self._running = True
        if sys.platform == "win32":
            self._run_windows()
        else:
            self._run_linux()

    def _run_windows(self):
        # Listen with keyboard hook events instead of polling keyboard.is_pressed():
        # polling every 50 ms delayed both edges and could miss a short tap (plan 0006).
        try:
            self._install_hooks()
        except Exception as e:
            _log.error(f"Hotkey could not be registered: {e}")
            self.error_occurred.emit("osd.hotkey_failed")
            return
        try:
            while self._running:
                time.sleep(0.1)
        finally:
            self._remove_hooks()

    def _install_hooks(self) -> None:
        """Press hook on the main key; release hooks on every part of a combination
        ("ctrl+space"), so releasing any part ends the recording, as polling did."""
        import keyboard
        parts = [p.strip() for p in self._key.split("+") if p.strip()]
        self._modifiers = parts[:-1]
        self._hooks = [keyboard.on_press_key(parts[-1], self._on_main_key_down)]
        for part in parts:
            self._hooks.append(keyboard.on_release_key(part, self._on_key_part_up))

    def _remove_hooks(self) -> None:
        import keyboard
        for hook in self._hooks:
            try:
                keyboard.unhook(hook)
            except Exception:
                pass
        self._hooks = []

    def _on_main_key_down(self, _event=None) -> None:
        import keyboard
        if self._paused or self._is_key_down:
            return  # held key: Windows repeats the press event
        if not all(keyboard.is_pressed(m) for m in self._modifiers):
            return
        self._is_key_down = True
        self.hotkey_pressed.emit()

    def _on_key_part_up(self, _event=None) -> None:
        if self._paused or not self._is_key_down:
            return
        self._is_key_down = False
        self.hotkey_released.emit()

    def _run_linux(self):
        from pynput import keyboard as pynput_kb

        def _canonical_key(key):
            try:
                return key.char.lower() if hasattr(key, "char") and key.char else str(key).lower()
            except Exception:
                return str(key).lower()

        def on_press(key) -> None:
            k = _canonical_key(key)
            if k == self._key and not self._paused and not self._is_key_down:
                self._is_key_down = True
                self.hotkey_pressed.emit()

        def on_release(key) -> None:
            k = _canonical_key(key)
            if k == self._key and not self._paused and self._is_key_down:
                self._is_key_down = False
                self.hotkey_released.emit()

        try:
            listener = pynput_kb.Listener(on_press=on_press, on_release=on_release)
            listener.start()
            while self._running:
                time.sleep(0.1)
            listener.stop()
        except Exception:
            _log.error("Hotkey crashed")
            self.error_occurred.emit("osd.hotkey_failed")

    def set_key(self, key: str):
        self._key         = key.lower()
        self._is_key_down = False
        if self._hooks:  # listening on Windows: move the hooks to the new key
            self._remove_hooks()
            try:
                self._install_hooks()
            except Exception as e:
                _log.error(f"Hotkey could not be registered: {e}")
                self.error_occurred.emit("osd.hotkey_failed")

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
