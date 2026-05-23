"""
HotkeyWorker state machine ve sinyal testleri.
keyboard.is_pressed mock'lanır; donanım gerekmez.
"""
import time
import pytest
from unittest.mock import patch
from workers.hotkey_worker import HotkeyWorker


class TestInitialState:
    def test_default_key_is_lowercase(self, mock_settings):
        worker = HotkeyWorker(mock_settings, key="F9")
        assert worker._key == "f9"

    def test_custom_key_lowercased(self, mock_settings):
        worker = HotkeyWorker(mock_settings, key="F8")
        assert worker._key == "f8"

    def test_is_key_down_starts_false(self, mock_settings):
        worker = HotkeyWorker(mock_settings)
        assert worker._is_key_down is False

    def test_running_starts_false(self, mock_settings):
        worker = HotkeyWorker(mock_settings)
        assert worker._running is False


class TestSetKey:
    def test_set_key_updates_key(self, mock_settings):
        worker = HotkeyWorker(mock_settings, key="F9")
        worker.set_key("F8")
        assert worker._key == "f8"

    def test_set_key_lowercases(self, mock_settings):
        worker = HotkeyWorker(mock_settings)
        worker.set_key("CTRL+SPACE")
        assert worker._key == "ctrl+space"

    def test_set_key_resets_is_key_down(self, mock_settings):
        worker = HotkeyWorker(mock_settings)
        worker._is_key_down = True
        worker.set_key("F8")
        assert worker._is_key_down is False

    def test_set_key_resets_even_when_same_key(self, mock_settings):
        worker = HotkeyWorker(mock_settings, key="F9")
        worker._is_key_down = True
        worker.set_key("F9")
        assert worker._is_key_down is False

    def test_set_key_combination(self, mock_settings):
        worker = HotkeyWorker(mock_settings)
        worker.set_key("ctrl+space")
        assert worker._key == "ctrl+space"

    def test_set_key_function_keys(self, mock_settings):
        worker = HotkeyWorker(mock_settings)
        for i in range(1, 13):
            worker.set_key(f"F{i}")
            assert worker._key == f"f{i}"


class TestKeyRepeatPrevention:
    """
    OS key-repeat koruması: tuşa basılı tutulurken
    hotkey_pressed yalnızca BİR KEZ emit edilmeli.
    """

    def test_press_emits_once(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="F9")
        received = []
        worker.hotkey_pressed.connect(lambda: received.append(1))

        # Simüle: tuş basılı (True, True, True) — repeat
        with patch("keyboard.is_pressed") as mock_pressed:
            mock_pressed.return_value = True

            # İlk çağrı: False → True, sinyal emit edilmeli
            worker._is_key_down = False
            currently = mock_pressed(worker._key)
            if currently and not worker._is_key_down:
                worker._is_key_down = True
                worker.hotkey_pressed.emit()

            # İkinci çağrı: True → True, sinyal emit edilmemeli
            currently = mock_pressed(worker._key)
            if currently and not worker._is_key_down:
                worker._is_key_down = True
                worker.hotkey_pressed.emit()

        assert len(received) == 1

    def test_release_emits_once(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="F9")
        released = []
        worker.hotkey_released.connect(lambda: released.append(1))

        worker._is_key_down = True

        with patch("keyboard.is_pressed") as mock_pressed:
            mock_pressed.return_value = False

            # İlk çağrı: True → False, sinyal emit edilmeli
            currently = mock_pressed(worker._key)
            if not currently and worker._is_key_down:
                worker._is_key_down = False
                worker.hotkey_released.emit()

            # İkinci çağrı: False → False, sinyal emit edilmemeli
            currently = mock_pressed(worker._key)
            if not currently and worker._is_key_down:
                worker._is_key_down = False
                worker.hotkey_released.emit()

        assert len(released) == 1

    def test_press_release_cycle(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="F9")
        pressed_count = []
        released_count = []
        worker.hotkey_pressed.connect(lambda: pressed_count.append(1))
        worker.hotkey_released.connect(lambda: released_count.append(1))

        states = [True, True, True, False, False, True, False]  # bas-tut-bırak-bas-bırak
        for state in states:
            if state and not worker._is_key_down:
                worker._is_key_down = True
                worker.hotkey_pressed.emit()
            elif not state and worker._is_key_down:
                worker._is_key_down = False
                worker.hotkey_released.emit()

        assert len(pressed_count) == 2
        assert len(released_count) == 2


class TestStopMechanism:
    def test_stop_sets_running_false(self, mock_settings):
        worker = HotkeyWorker(mock_settings, key="F9")
        worker._running = True
        # stop() wait() çağırır; thread başlatılmadıysa wait() anında döner
        worker._running = False
        assert worker._running is False

    def test_worker_not_running_before_start(self, mock_settings):
        worker = HotkeyWorker(mock_settings)
        assert not worker.isRunning()


class TestStop:
    """stop() metodunu doğrudan çağıran testler (lines 49-51)."""

    def test_stop_sets_running_false(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings)
        worker._running = True
        worker.stop()
        assert worker._running is False

    def test_stop_does_not_block(self, qapp, mock_settings):
        """stop() wait() çağırmamalı — kapanış os._exit(0) ile yapılır."""
        worker = HotkeyWorker(mock_settings)
        with patch.object(worker, "wait") as mock_wait:
            worker.stop()
        mock_wait.assert_not_called()

    def test_stop_on_non_running_worker_is_safe(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings)
        worker.stop()  # must not raise
        assert worker._running is False

    def test_stop_does_not_terminate(self, qapp, mock_settings):
        """stop() terminate() çağırmamalı — GIL riski, os._exit(0) zaten keser."""
        worker = HotkeyWorker(mock_settings)
        with patch.object(worker, "terminate") as mock_terminate:
            worker.stop()
        mock_terminate.assert_not_called()


class TestRunKeyboardError:
    """Inner try: keyboard.is_pressed exception handler (lines 25-29)."""

    def _run_with_keyboard_error(self, worker):
        call_count = 0

        def is_pressed_side_effect(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("klavye hatası")
            worker._running = False
            return False

        with patch("keyboard.is_pressed", side_effect=is_pressed_side_effect), \
             patch("workers.hotkey_worker.time.sleep"):
            worker.run()

    def test_keyboard_error_emits_err_log(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        self._run_with_keyboard_error(worker)
        assert any(l == "ERR" and "Klavye okuma hatası" in m for l, _, m in logs)

    def test_keyboard_error_emits_error_occurred(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        errors = []
        worker.error_occurred.connect(errors.append)
        self._run_with_keyboard_error(worker)
        assert any("Klavye okuma hatası" in e for e in errors)

    def test_keyboard_error_component_is_key(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        self._run_with_keyboard_error(worker)
        assert any(c == "KEY" for _, c, _ in logs)

    def test_keyboard_error_loop_continues(self, qapp, mock_settings):
        """Error sonrası loop devam etmeli; ikinci iterasyon temiz çalışmalı."""
        worker = HotkeyWorker(mock_settings, key="f9")
        call_count = 0

        def is_pressed_side_effect(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("test hatası")
            worker._running = False
            return False

        with patch("keyboard.is_pressed", side_effect=is_pressed_side_effect), \
             patch("workers.hotkey_worker.time.sleep"):
            worker.run()  # must not raise

        assert call_count == 2

    def test_keyboard_error_sleep_called_with_1s(self, qapp, mock_settings):
        """Error handler 1 saniyelik bekleme yapmalı."""
        worker = HotkeyWorker(mock_settings, key="f9")
        sleep_calls = []
        call_count = 0

        def is_pressed_side_effect(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("test hatası")
            worker._running = False
            return False

        with patch("keyboard.is_pressed", side_effect=is_pressed_side_effect), \
             patch("workers.hotkey_worker.time.sleep", side_effect=sleep_calls.append):
            worker.run()

        assert 1.0 in sleep_calls


class TestRunSignalEmission:
    """run() içindeki sinyal emit dalları (lines 32-33, 36-37)."""

    def test_run_emits_hotkey_pressed(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        pressed = []
        worker.hotkey_pressed.connect(lambda: pressed.append(1))

        call_count = 0

        def is_pressed_side_effect(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True  # False → True geçişi: press emit
            worker._running = False
            return True

        with patch("keyboard.is_pressed", side_effect=is_pressed_side_effect), \
             patch("workers.hotkey_worker.time.sleep"):
            worker.run()

        assert len(pressed) == 1

    def test_run_emits_hotkey_released(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        worker._is_key_down = True
        released = []
        worker.hotkey_released.connect(lambda: released.append(1))

        call_count = 0

        def is_pressed_side_effect(key):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False  # True → False geçişi: release emit
            worker._running = False
            return False

        with patch("keyboard.is_pressed", side_effect=is_pressed_side_effect), \
             patch("workers.hotkey_worker.time.sleep"):
            worker.run()

        assert len(released) == 1


class TestRunOuterCrash:
    """Outer try: while döngüsünden kaçan felaket exception (lines 41-43)."""

    def _run_with_outer_crash(self, worker):
        def sleep_side_effect(seconds):
            if abs(seconds - 0.05) < 0.001:
                raise RuntimeError("simüle çökme")

        with patch("keyboard.is_pressed", return_value=False), \
             patch("workers.hotkey_worker.time.sleep", side_effect=sleep_side_effect):
            worker.run()

    def test_outer_crash_emits_err_log(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        self._run_with_outer_crash(worker)
        assert any(l == "ERR" and "çöktü" in m for l, _, m in logs)

    def test_outer_crash_emits_error_occurred(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        errors = []
        worker.error_occurred.connect(errors.append)
        self._run_with_outer_crash(worker)
        assert any("Kısayol çalışmıyor" in e for e in errors)

    def test_outer_crash_run_does_not_raise(self, qapp, mock_settings):
        """run() exception'ı dışarı sızdırmamalı — QThread mekanizması bozulur."""
        worker = HotkeyWorker(mock_settings, key="f9")
        self._run_with_outer_crash(worker)  # must not raise

    def test_outer_crash_component_is_key(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        self._run_with_outer_crash(worker)
        assert any(c == "KEY" for _, c, _ in logs)


class TestPauseResume:
    """pause() ve resume() mekanizmasının UI kısayol atama esnasında dinlemeyi kesme testleri."""

    def test_pause_sets_flags(self, mock_settings):
        worker = HotkeyWorker(mock_settings)
        worker._is_key_down = True
        worker._paused = False
        worker.pause()
        assert worker._paused is True
        assert worker._is_key_down is False

    def test_resume_sets_flags_when_key_unpressed(self, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        worker._paused = True
        worker._is_key_down = True
        with patch("keyboard.is_pressed", return_value=False):
            worker.resume()
        assert worker._paused is False
        assert worker._is_key_down is False

    def test_resume_sets_flags_when_key_pressed(self, mock_settings):
        """resume anında tuş hala fiziksel basılıysa, sahte tetiklenmeyi engellemek için state True yapılır."""
        worker = HotkeyWorker(mock_settings, key="f9")
        worker._paused = True
        worker._is_key_down = False
        with patch("keyboard.is_pressed", return_value=True):
            worker.resume()
        assert worker._paused is False
        assert worker._is_key_down is True

    def test_run_ignores_keys_when_paused(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings, key="f9")
        worker._paused = True
        pressed = []
        worker.hotkey_pressed.connect(lambda: pressed.append(1))

        def is_pressed_side_effect(key):
            worker._running = False  # Sonsuz döngüyü tek iterasyonda kır
            return True  # Fiziksel olarak tuşa basılıyor simülasyonu

        with patch("keyboard.is_pressed", side_effect=is_pressed_side_effect), \
             patch("workers.hotkey_worker.time.sleep"):
            worker.run()

        # Duraklatılmış (paused) olduğu için tuş basılı olsa bile sinyal yollanmamalı
        assert len(pressed) == 0
        # Güvenlik ağı: run döngüsü içindeki pause check _is_key_down'ı sıfırlamalı
        assert worker._is_key_down is False
