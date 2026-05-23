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
                    self.log_entry.emit("ERR", "KEY", "Klavye okuma hatası")
                    self.error_occurred.emit("Klavye okuma hatası")
                    time.sleep(1.0)
                    continue

                if self._paused:
                    self._is_key_down = False  # duraklatıldığında state'i temizle
                    time.sleep(0.05)
                    continue

                if currently_down and not self._is_key_down:
                    self._is_key_down = True
                    self.hotkey_pressed.emit()

                elif not currently_down and self._is_key_down:
                    self._is_key_down = False
                    self.hotkey_released.emit()

                time.sleep(0.05)  # 50 ms polling — CPU dostu

        except Exception:
            self.log_entry.emit("ERR", "KEY", "Kısayol tuşu çöktü")
            self.error_occurred.emit("Kısayol çalışmıyor")

    def set_key(self, key: str):
        self._key         = key.lower()
        self._is_key_down = False   # yarım kalmış state'i sıfırla

    def pause(self) -> None:
        """Kısayol yakalama modu gibi durumlarda hotkey'i geçici olarak devre dışı bırakır."""
        self._paused = True
        self._is_key_down = False

    def resume(self) -> None:
        """Hotkey dinlemeyi yeniden etkinleştirir.
        
        Tuş hâlâ fiziksel olarak basılıysa _is_key_down=True yaparak worker'ı
        'zaten tutuluydu' moduna alır. Bir sonraki hotkey_pressed ancak tuş
        bırakılıp tekrar basıldığında tetiklenir — sihirli timer gerekmez.
        """
        import keyboard
        self._is_key_down = keyboard.is_pressed(self._key)
        self._paused = False

    def stop(self) -> None:
        self._running = False
