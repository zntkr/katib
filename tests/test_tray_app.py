"""TrayApp: the tray icon and its menu, the status it shows and what the hotkey does (ADR-0012).
Also qt_key_to_keyboard, the pure key-name conversion the hotkey capture uses."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSystemTrayIcon

from core.i18n import t
from core.models import ModelProvider
from core.settings import (
    MSG_MIC_UNAVAILABLE, MSG_MODEL_NOT_FOUND, STATE_LISTENING, STATE_LOADING,
    STATE_PROCESSING, STATE_READY,
)
from ui.settings_window import TABS
from ui.tray_app import TrayApp
from ui.utils import qt_key_to_keyboard

TRAY_AVAILABLE = "ui.tray_app.QSystemTrayIcon.isSystemTrayAvailable"


class TestQtKeyToKeyboard:
    @pytest.mark.parametrize("number", range(1, 13))
    def test_function_keys(self, number):
        assert qt_key_to_keyboard(getattr(Qt.Key, f"Key_F{number}")) == f"f{number}"

    @pytest.mark.parametrize("key, name", [
        (Qt.Key.Key_Space, "space"), (Qt.Key.Key_Return, "enter"), (Qt.Key.Key_Escape, "esc"),
        (Qt.Key.Key_Tab, "tab"), (Qt.Key.Key_Backspace, "backspace"), (Qt.Key.Key_Delete, "delete"),
        (Qt.Key.Key_Insert, "insert"), (Qt.Key.Key_Home, "home"), (Qt.Key.Key_End, "end"),
        (Qt.Key.Key_PageUp, "page up"), (Qt.Key.Key_PageDown, "page down"),
        (Qt.Key.Key_Up, "up"), (Qt.Key.Key_Down, "down"), (Qt.Key.Key_Left, "left"), (Qt.Key.Key_Right, "right"),
    ])
    def test_named_keys(self, key, name):
        assert qt_key_to_keyboard(key) == name

    def test_letters_and_digits_are_lowercase(self):
        assert qt_key_to_keyboard(Qt.Key.Key_A) == "a"
        assert qt_key_to_keyboard(Qt.Key.Key_5) == "5"

    def test_a_key_with_no_name_gives_none(self):
        assert qt_key_to_keyboard(Qt.Key.Key_Control) is None


def _make(mock_settings) -> TrayApp:
    """A TrayApp on a machine that has a system tray, whatever the test machine offers."""
    with patch(TRAY_AVAILABLE, return_value=True):
        return TrayApp(mock_settings, ModelProvider("."))


def _close(app: TrayApp) -> None:
    app.tray.hide()
    app.settings_window.close()
    for window in _help_windows():
        window.close()


def _help_windows() -> list:
    from PySide6.QtWidgets import QApplication
    from ui.help_window import HelpWindow
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, HelpWindow) and w.isVisible()]


@pytest.fixture
def tray(qapp, mock_settings):
    app = _make(mock_settings)
    app.audio_worker = MagicMock()
    app.osd = MagicMock()
    app.transcription_worker = MagicMock(is_ready=True, is_loading=False)
    yield app
    _close(app)


def _shows(app: TrayApp, key: str) -> bool:
    return t(key) in app.tray.toolTip()


def _recording_icon(app: TrayApp) -> bool:
    return app.tray.icon().cacheKey() != app.icon_idle.cacheKey()


def _action(app: TrayApp, text_key: str):
    return next(a for a in app.tray.contextMenu().actions() if a.text() == t(text_key))


class TestStartup:
    def test_no_window_opens(self, tray):
        """ADR-0012: the tray icon and the pill are the interface; nothing opens by itself."""
        assert not tray.settings_window.isVisible()
        assert tray.settings_window.btn_quit.isHidden()  # the tray menu is where one quits

    def test_status_says_loading_until_the_model_reports(self, tray):
        assert _shows(tray, STATE_LOADING)

    def test_a_missing_model_opens_the_settings_where_one_can_be_chosen(self, tray):
        tray.on_model_missing()
        assert tray.settings_window.isVisible()
        assert tray.settings_window.tabs.currentIndex() == TABS.index("dictation")

    def test_workers_are_attached_after_construction(self, qapp, mock_settings):
        app = _make(mock_settings)
        audio, transcription, osd = MagicMock(), MagicMock(), MagicMock()
        app.attach_workers(audio_worker=audio, transcription_worker=transcription, osd=osd)
        assert (app.audio_worker, app.transcription_worker, app.osd) == (audio, transcription, osd)
        _close(app)


class TestMenu:
    def test_offers_settings_guide_copy_and_quit(self, tray):
        texts = [a.text() for a in tray.tray.contextMenu().actions() if not a.isSeparator()]
        assert texts == ["Settings", "User Guide", "Copy last transcript", "Quit"]

    def test_settings_opens_the_settings_window(self, tray):
        _action(tray, "tray.menu.settings").trigger()
        assert tray.settings_window.isVisible()

    def test_double_click_opens_the_settings_window(self, tray):
        tray.tray.activated.emit(QSystemTrayIcon.ActivationReason.DoubleClick)
        assert tray.settings_window.isVisible()

    def test_a_single_click_opens_nothing(self, tray):
        tray.tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
        assert not tray.settings_window.isVisible()

    def test_user_guide_opens_one_help_window(self, tray):
        _action(tray, "tray.menu.user_guide").trigger()
        _action(tray, "tray.menu.user_guide").trigger()
        assert len(_help_windows()) == 1

    def test_copy_is_offered_once_something_was_dictated(self, tray):
        assert not _action(tray, "tray.menu.copy_transcript").isEnabled()
        with patch("ui.tray_app.inject_text"):
            tray.on_text_ready("merhaba dünya")
        assert _action(tray, "tray.menu.copy_transcript").isEnabled()

    def test_copy_puts_the_last_dictation_on_the_clipboard(self, tray):
        with patch("ui.tray_app.inject_text"):
            tray.on_text_ready("first")
            tray.on_text_ready("merhaba dünya")
        with patch("ui.tray_app.QApplication.clipboard") as clipboard:
            _action(tray, "tray.menu.copy_transcript").trigger()
        clipboard.return_value.setText.assert_called_once_with("merhaba dünya")


class TestDictation:
    def test_text_is_written_with_the_chosen_method(self, tray, mock_settings):
        mock_settings.set("injection_method", "keystroke")
        with patch("ui.tray_app.inject_text") as inject:
            tray.on_text_ready("merhaba")
        inject.assert_called_once_with("merhaba", injection_method="keystroke")

    def test_hotkey_press_starts_recording(self, tray):
        tray.on_hotkey_pressed()
        tray.audio_worker.start_recording.assert_called_once()
        tray.osd.setStateRecording.assert_called_once()
        assert _shows(tray, STATE_LISTENING) and _recording_icon(tray)

    def test_hotkey_release_stops_recording(self, tray):
        tray.on_hotkey_pressed()
        tray.on_hotkey_released()
        tray.audio_worker.stop_recording.assert_called_once()
        assert not _shows(tray, STATE_LISTENING) and not _recording_icon(tray)

    def test_hotkey_while_the_model_loads_says_loading(self, tray):
        tray.transcription_worker = MagicMock(is_ready=False, is_loading=True)
        tray.on_hotkey_pressed()
        tray.osd.setStateError.assert_called_once_with(STATE_LOADING)
        tray.audio_worker.start_recording.assert_not_called()
        assert not _shows(tray, STATE_LISTENING)

    def test_hotkey_without_a_model_says_no_model(self, tray):
        tray.transcription_worker = MagicMock(is_ready=False, is_loading=False)
        tray.on_hotkey_pressed()
        tray.osd.setStateError.assert_called_once_with(MSG_MODEL_NOT_FOUND)
        tray.audio_worker.start_recording.assert_not_called()

    def test_level_reaches_the_settings_window_while_recording(self, tray):
        tray.on_hotkey_pressed()
        tray.on_level_changed(0.5)
        assert tray.settings_window.level_bar.value() == 50

    def test_a_level_arriving_after_the_recording_is_dropped(self, tray):
        tray.on_hotkey_pressed()
        tray.on_level_changed(0.5)
        tray.on_hotkey_released()
        tray.on_level_changed(0.7)
        assert tray.settings_window.level_bar.value() == 0


class TestStatus:
    """TrayApp is the only writer of the tray tooltip and icon; one priority rule decides:
    recording > processing > download notice > no microphone > model status."""

    def test_model_status_is_shown(self, tray):
        tray.on_model_status(STATE_READY, "OK")
        assert _shows(tray, STATE_READY)
        tray.on_model_status(MSG_MODEL_NOT_FOUND, "WARN")
        assert _shows(tray, MSG_MODEL_NOT_FOUND)

    def test_model_error_is_not_reported_as_missing_model(self, tray):
        tray.on_model_status("status.model_error", "ERR")
        assert _shows(tray, "status.model_error")

    def test_missing_microphone_is_shown(self, tray):
        tray.on_mic_unavailable()
        assert _shows(tray, MSG_MIC_UNAVAILABLE)

    def test_model_ready_does_not_hide_missing_microphone(self, tray):
        """The original bug: started without a mic, the model finished loading and showed 'Ready'."""
        tray.on_mic_unavailable()
        tray.on_model_status(STATE_READY, "OK")
        assert _shows(tray, MSG_MIC_UNAVAILABLE)

    def test_microphone_coming_back_shows_the_model_status_again(self, tray):
        tray.on_model_status(STATE_READY, "OK")
        tray.on_mic_unavailable()
        tray.on_mic_available()
        assert _shows(tray, STATE_READY)

    def test_finished_transcription_does_not_hide_missing_microphone(self, tray):
        tray.on_model_status(STATE_READY, "OK")
        tray.on_transcription_started()
        tray.on_mic_unavailable()
        tray.on_transcription_finished()
        assert _shows(tray, MSG_MIC_UNAVAILABLE)

    def test_processing_shown_while_transcribing(self, tray):
        tray.on_model_status(STATE_READY, "OK")
        tray.on_transcription_started()
        assert _shows(tray, STATE_PROCESSING)
        tray.on_transcription_finished()
        assert _shows(tray, STATE_READY)

    def test_mic_failure_when_recording_starts_shows_no_mic(self, tray):
        tray.set_recording(True)
        tray.on_mic_unavailable()
        assert _shows(tray, MSG_MIC_UNAVAILABLE) and not _recording_icon(tray)

    def test_recording_wins_over_model_updates(self, tray):
        tray.set_recording(True)
        tray.on_model_status(STATE_LOADING, "IDLE")
        assert _shows(tray, STATE_LISTENING)

    def test_recording_keeps_notice_while_download_runs(self, tray):
        """Plan 0003 Faz 1: dictating during a download must not hide 'Downloading...'."""
        tray.on_download_state(True)
        tray.on_download_status("status.downloading_model", "INFO")
        tray.set_recording(True)
        tray.set_recording(False)
        assert _shows(tray, "status.downloading_model")

    def test_recording_clears_finished_download_error(self, tray):
        tray.on_model_status(STATE_READY, "OK")
        tray.on_download_state(True)
        tray.on_download_status("status.download_error", "ERR")
        tray.on_download_state(False)
        tray.set_recording(True)
        tray.set_recording(False)
        assert _shows(tray, STATE_READY)

    def test_download_notice_until_newer_model_status(self, tray):
        tray.on_download_status("status.downloading_model", "INFO")
        assert _shows(tray, "status.downloading_model")
        tray.on_download_status("status.download_error", "ERR")
        assert _shows(tray, "status.download_error")
        tray.on_model_status(STATE_READY, "OK")
        assert _shows(tray, STATE_READY)


class TestLanguageChange:
    def test_menu_and_settings_window_follow_the_language(self, tray):
        tray.apply_language("tr")
        texts = [a.text() for a in tray.tray.contextMenu().actions() if not a.isSeparator()]
        assert texts[0] == "Ayarlar"
        assert tray.settings_window.tabs.tabText(TABS.index("dictation")) == "Dikte"
        tray.osd.refresh_language.assert_called_once()

    def test_keeps_no_mic_tooltip(self, tray):
        """Plan 0003 Faz 2: rebuilding the tray must not reset it to 'Ready'."""
        tray.on_mic_unavailable()
        tray.apply_language("en")
        assert _shows(tray, MSG_MIC_UNAVAILABLE)

    def test_keeps_the_recording_icon(self, tray):
        tray.set_recording(True)
        tray.apply_language("en")
        assert _recording_icon(tray)

    def test_keeps_the_copy_action_available(self, tray):
        with patch("ui.tray_app.inject_text"):
            tray.on_text_ready("merhaba")
        tray.apply_language("en")
        assert _action(tray, "tray.menu.copy_transcript").isEnabled()

    def test_the_user_guide_is_built_again_in_the_new_language(self, tray):
        tray.show_help()
        tray.apply_language("tr")
        assert _help_windows() == []
        tray.show_help()
        assert ["Kullanım Kılavuzu" in w.windowTitle() for w in _help_windows()] == [True]


class TestWithoutSystemTray:
    """No system tray at startup, e.g. autostart before Explorer has created the taskbar."""

    @pytest.fixture
    def tray(self, qapp, mock_settings, monkeypatch):
        monkeypatch.setattr(TrayApp, "TRAY_RETRY_LIMIT", 3)
        with patch(TRAY_AVAILABLE, return_value=False):
            app = TrayApp(mock_settings, ModelProvider("."))
            app.audio_worker = MagicMock()
            yield app
        _close(app)

    def test_the_settings_window_opens_as_the_only_way_in_and_out(self, tray):
        window = tray.settings_window
        assert window.isVisible()
        assert window.tabs.currentIndex() == TABS.index("app")
        assert window.btn_quit.isVisible()

    def test_the_hotkey_still_works(self, tray):
        tray.on_hotkey_pressed()
        tray.audio_worker.start_recording.assert_called_once()
        tray.on_mic_unavailable()
        tray.on_mic_available()

    @staticmethod
    def _retry(tray, times: int = 1) -> None:
        """The retry timer firing, without waiting for the clock."""
        for _ in range(times):
            tray._tray_retry_timer.timeout.emit()

    def test_it_keeps_looking_while_there_is_no_tray(self, tray):
        self._retry(tray, 2)
        assert tray._tray_retry_timer.isActive()

    def test_the_icon_appears_once_the_tray_exists(self, tray):
        with patch(TRAY_AVAILABLE, return_value=True), patch.object(tray.tray, "show") as show:
            self._retry(tray)
        show.assert_called_once()
        assert not tray._tray_retry_timer.isActive()
        assert tray.settings_window.btn_quit.isHidden()  # the tray menu quits from now on

    def test_it_stops_looking_after_the_retry_limit(self, tray):
        self._retry(tray, 3)
        assert not tray._tray_retry_timer.isActive()

    def test_language_change_works_without_a_tray(self, tray):
        tray.apply_language("en")
        tray.set_recording(True)
        assert _shows(tray, STATE_LISTENING)
