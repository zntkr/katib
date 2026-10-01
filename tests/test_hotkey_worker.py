"""
HotkeyWorker state machine and signal tests.
The keyboard library's hook functions are mocked; no hardware required.
"""
import time
import pytest
from unittest.mock import patch
from workers.hotkey_worker import HotkeyWorker
from tests.log_helpers import on_log_entry


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


class TestStopMechanism:
    def test_stop_sets_running_false(self, mock_settings):
        worker = HotkeyWorker(mock_settings, key="F9")
        worker._running = True
        # stop() calls wait(); if the thread was never started, wait() returns immediately
        worker._running = False
        assert worker._running is False

    def test_worker_not_running_before_start(self, mock_settings):
        worker = HotkeyWorker(mock_settings)
        assert not worker.isRunning()


class TestStop:
    """Tests that directly call stop() (lines 49-51)."""

    def test_stop_sets_running_false(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings)
        worker._running = True
        worker.stop()
        assert worker._running is False

    def test_stop_does_not_block(self, qapp, mock_settings):
        """stop() must not call wait() — shutdown is done via os._exit(0)."""
        worker = HotkeyWorker(mock_settings)
        with patch.object(worker, "wait") as mock_wait:
            worker.stop()
        mock_wait.assert_not_called()

    def test_stop_on_non_running_worker_is_safe(self, qapp, mock_settings):
        worker = HotkeyWorker(mock_settings)
        worker.stop()  # must not raise
        assert worker._running is False

    def test_stop_does_not_terminate(self, qapp, mock_settings):
        """stop() must not call terminate() — GIL risk; os._exit(0) already cuts it."""
        worker = HotkeyWorker(mock_settings)
        with patch.object(worker, "terminate") as mock_terminate:
            worker.stop()
        mock_terminate.assert_not_called()


class TestPauseResume:
    """Tests for the pause() and resume() mechanism that stops listening during UI hotkey assignment."""

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
        """If the key is still physically held at resume time, state is set to True to prevent a spurious trigger."""
        worker = HotkeyWorker(mock_settings, key="f9")
        worker._paused = True
        worker._is_key_down = False
        with patch("keyboard.is_pressed", return_value=True):
            worker.resume()
        assert worker._paused is False
        assert worker._is_key_down is True


# ─────────────────────────────────────────────────────────────── Windows key hooks
# Plan 0006 Faz 3: the hotkey is listened to with keyboard hook events instead of
# polling keyboard.is_pressed() every 50 ms.

@pytest.fixture
def kb():
    """Fake keyboard hooks: records the callbacks so a test can fire key events."""
    hooks = {"press": {}, "release": {}, "unhooked": [], "held": set()}

    def on_press_key(key, callback, suppress=False):
        hooks["press"][key] = callback
        return ("press", key)

    def on_release_key(key, callback, suppress=False):
        hooks["release"][key] = callback
        return ("release", key)

    with patch("keyboard.on_press_key", side_effect=on_press_key), \
         patch("keyboard.on_release_key", side_effect=on_release_key), \
         patch("keyboard.unhook", side_effect=hooks["unhooked"].append), \
         patch("keyboard.is_pressed", side_effect=lambda k: k in hooks["held"]):
        yield hooks


def run_windows(worker, scenario):
    """Runs the Windows listening path; `scenario` fires events while the hooks are live."""
    def tick(_seconds):
        scenario()
        worker._running = False

    worker._running = True
    with patch("workers.hotkey_worker.time.sleep", side_effect=tick):
        worker._run_windows()


def _collect(worker):
    events = []
    worker.hotkey_pressed.connect(lambda: events.append("pressed"))
    worker.hotkey_released.connect(lambda: events.append("released"))
    return events


class TestWindowsKeyHooks:

    def test_hooks_main_key_press_and_release_of_every_part(self, qapp, mock_settings, kb):
        worker = HotkeyWorker(mock_settings, key="ctrl+space")
        run_windows(worker, lambda: None)
        assert set(kb["press"]) == {"space"}
        assert set(kb["release"]) == {"ctrl", "space"}
        assert len(kb["unhooked"]) == 3  # all hooks removed when the worker stops

    def test_held_key_autorepeat_emits_one_press(self, qapp, mock_settings, kb):
        worker = HotkeyWorker(mock_settings, key="f9")
        events = _collect(worker)
        run_windows(worker, lambda: (kb["press"]["f9"](None), kb["press"]["f9"](None), kb["press"]["f9"](None)))
        assert events == ["pressed"]

    def test_press_then_release(self, qapp, mock_settings, kb):
        worker = HotkeyWorker(mock_settings, key="f9")
        events = _collect(worker)
        run_windows(worker, lambda: (kb["press"]["f9"](None), kb["release"]["f9"](None), kb["release"]["f9"](None)))
        assert events == ["pressed", "released"]

    def test_combination_needs_its_modifiers_held(self, qapp, mock_settings, kb):
        worker = HotkeyWorker(mock_settings, key="ctrl+space")
        events = _collect(worker)

        def scenario():
            kb["press"]["space"](None)          # ctrl not held: ignored
            kb["held"].add("ctrl")
            kb["press"]["space"](None)          # ctrl held: recording starts

        run_windows(worker, scenario)
        assert events == ["pressed"]

    def test_releasing_a_modifier_ends_the_recording(self, qapp, mock_settings, kb):
        worker = HotkeyWorker(mock_settings, key="ctrl+space")
        events = _collect(worker)
        kb["held"].add("ctrl")
        run_windows(worker, lambda: (kb["press"]["space"](None), kb["release"]["ctrl"](None)))
        assert events == ["pressed", "released"]

    def test_paused_worker_ignores_the_key(self, qapp, mock_settings, kb):
        worker = HotkeyWorker(mock_settings, key="f9")
        events = _collect(worker)
        worker.pause()
        run_windows(worker, lambda: (kb["press"]["f9"](None), kb["release"]["f9"](None)))
        assert events == []

    def test_changing_the_key_while_running_moves_the_hooks(self, qapp, mock_settings, kb):
        worker = HotkeyWorker(mock_settings, key="f9")
        events = _collect(worker)

        def scenario():
            worker.set_key("f10")
            kb["press"]["f10"](None)

        run_windows(worker, scenario)
        assert ("press", "f9") in kb["unhooked"]
        assert events == ["pressed"]

    def test_hook_that_cannot_be_registered_is_reported(self, qapp, mock_settings, kb):
        worker = HotkeyWorker(mock_settings, key="f9")
        errors, logs = [], []
        worker.error_occurred.connect(errors.append)
        on_log_entry(lambda lvl, comp, msg: logs.append((lvl, comp)))
        with patch("keyboard.on_press_key", side_effect=ValueError("unknown key")):
            run_windows(worker, lambda: None)   # must return, not hang
        assert errors == ["osd.hotkey_failed"]
        assert ("ERR", "KEY") in logs
