"""SettingsWindow: the one window Katib has (ADR-0012). The tests drive it the way a user or
main.py does: through its widgets, its public methods and its signals."""
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt, QEvent, QRect
from PySide6.QtGui import QIcon, QKeyEvent, QPaintEvent, QPixmap
from PySide6.QtWidgets import QLabel, QMessageBox

from core.models import ModelProvider
from tests.log_helpers import on_log_entry
from ui.settings_window import SettingsWindow, TABS, LOG_LIMIT

MICS = [("USB Mic (Default)", 3, True), ("Headset", 5, False)]


def _key(key, modifiers=Qt.KeyboardModifier.NoModifier) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers)


def _select(combo, value) -> None:
    combo.setCurrentIndex(combo.findData(value))


def _button(window, text_key: str):
    from PySide6.QtWidgets import QPushButton
    from core.i18n import t
    return next(b for b in window.findChildren(QPushButton) if b.text() == t(text_key))


def _make_model(folder: Path) -> Path:
    folder.mkdir(parents=True)
    (folder / "config.json").write_text("{}")
    (folder / "model.bin").write_bytes(b"")
    return folder


@pytest.fixture
def models_root(tmp_path):
    """An empty models folder; the window and the provider both look here."""
    root = tmp_path / "Models"
    root.mkdir()
    with patch("ui.settings_window.DEFAULT_DOWNLOAD_PARENT", root):
        yield root


@pytest.fixture
def window(qapp, mock_settings, models_root):
    icon = QPixmap(1, 1)
    icon.fill(Qt.GlobalColor.transparent)
    mock_settings.set("model_dir", str(models_root))  # the default: the models root, no model yet
    w = SettingsWindow(mock_settings, ModelProvider(models_root), QIcon(icon))
    yield w
    w.close()
    w.deleteLater()


@pytest.fixture
def signals(window):
    """Everything the window emits, by signal name."""
    received: dict[str, list] = {}
    for name in ("device_changed", "hotkey_changed", "hotkey_capture_mode", "model_dir_changed",
                 "download_model_requested", "language_change_requested"):
        getattr(window, name).connect(lambda *args, n=name: received.setdefault(n, []).append(args))
    window.help_requested.connect(lambda: received.setdefault("help_requested", []).append(()))
    return received


class TestWindow:
    def test_has_three_tabs(self, window):
        assert window.tabs.count() == len(TABS)
        assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == ["Dictation", "App", "Log"]

    def test_show_tab_switches_by_name(self, window):
        window.show_tab("log")
        assert window.tabs.currentIndex() == TABS.index("log")

    def test_escape_hides_the_window(self, window):
        window.show()
        window.keyPressEvent(_key(Qt.Key.Key_Escape))
        assert not window.isVisible()

    def test_other_keys_leave_it_open(self, window):
        window.show()
        window.keyPressEvent(_key(Qt.Key.Key_A))
        assert window.isVisible()

    def test_opens_even_when_dark_title_bar_is_unavailable(self, window):
        with patch("ui.settings_window.apply_dark_mode_to_window", side_effect=Exception("No DWM")):
            window.show()
        assert window.isVisible()

    def test_paints_its_background(self, window):
        window.paintEvent(QPaintEvent(QRect(0, 0, 100, 100)))

    def test_shows_the_stored_settings_when_opened(self, window, mock_settings):
        mock_settings.set_many({"hotkey": "f10", "injection_method": "keystroke", "language": "tr"})
        window.show()
        assert window.btn_hotkey.text() == "F10"
        assert window.injection_combo.currentData() == "keystroke"
        assert window.speech_language_combo.currentData() == "tr"

    def test_opening_does_not_announce_changes(self, window, signals):
        window.show()
        assert signals == {}


class TestRebuild:
    """A language change builds the tabs again inside the same window object."""

    def test_tab_titles_follow_the_language(self, window):
        from core.i18n import set_language
        set_language("tr")
        window.rebuild()
        assert window.tabs.tabText(TABS.index("dictation")) == "Dikte"

    def test_signals_wired_from_outside_stay_connected(self, window, signals):
        window.rebuild()
        other = "de" if window.app_language_combo.currentData() != "de" else "fr"
        _select(window.app_language_combo, other)
        assert signals["language_change_requested"] == [(other,)]

    def test_keeps_the_open_tab_and_everything_the_workers_reported(self, window):
        window.populate_devices(MICS)
        window.append_log_entry("OK", "STT", "Model ready")
        window.show_last_recording(4.0, -48.0, -71.0, "")
        window.on_model_loaded("cuda", "float16", "")
        window.show_last_dictation(4.0, 0.3)
        window.show_tab("log")
        window.rebuild()
        assert window.tabs.currentIndex() == TABS.index("log")
        assert window.mic_combo.count() == 2
        assert "Model ready" in window.log_box.toPlainText()
        assert "-48 dB" in window.lbl_recording.text()
        assert "GPU" in window.lbl_model_info.text() and "0.3 s" in window.lbl_model_info.text()

    def test_does_not_report_the_microphone_again(self, window, signals):
        """device_changed clears the 'no microphone' status; a rebuild must not send it."""
        window.populate_devices(MICS)
        signals.clear()
        window.rebuild()
        assert "device_changed" not in signals

    def test_cancels_a_hotkey_capture_in_progress(self, window, signals):
        window.btn_hotkey.click()
        window.rebuild()
        assert signals["hotkey_capture_mode"] == [(True,), (False,)]
        assert window.btn_hotkey.text() == "F9"


class TestHotkey:
    def test_clicking_the_hotkey_button_waits_for_a_key(self, window, signals):
        window.btn_hotkey.click()
        assert window.btn_hotkey.text() == "Press a key..."
        assert signals["hotkey_capture_mode"] == [(True,)]

    def test_the_next_key_becomes_the_hotkey(self, window, mock_settings, signals):
        window.btn_hotkey.click()
        window.keyPressEvent(_key(Qt.Key.Key_F10))
        assert mock_settings.get("hotkey") == "f10"
        assert window.btn_hotkey.text() == "F10"
        assert signals["hotkey_changed"] == [("f10",)]
        assert signals["hotkey_capture_mode"] == [(True,), (False,)]

    def test_modifiers_are_part_of_the_hotkey(self, window, mock_settings):
        window.btn_hotkey.click()
        window.keyPressEvent(_key(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier))
        assert mock_settings.get("hotkey") == "ctrl+a"

    def test_a_modifier_alone_keeps_waiting(self, window, signals):
        window.btn_hotkey.click()
        window.keyPressEvent(_key(Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier))
        assert window.btn_hotkey.text() == "Press a key..."
        assert "hotkey_changed" not in signals

    def test_escape_cancels_the_capture_and_keeps_the_window_open(self, window, mock_settings, signals):
        window.show()
        window.btn_hotkey.click()
        window.keyPressEvent(_key(Qt.Key.Key_Escape))
        assert mock_settings.get("hotkey") == "f9"
        assert window.btn_hotkey.text() == "F9"
        assert window.isVisible()
        assert "hotkey_changed" not in signals


class TestAppTab:
    def test_offers_no_theme_choice(self, window):
        """The app is dark only (ADR-0013)."""
        assert not hasattr(window, "theme_combo")
        assert not hasattr(window, "theme_changed")
        labels = [label.text() for label in window.tabs.widget(TABS.index("app")).findChildren(QLabel)]
        assert labels == ["App Language", "Text Injection Method"]

    def test_app_language_choice_is_saved_and_announced(self, window, mock_settings, signals):
        other = "de" if window.app_language_combo.currentData() != "de" else "fr"
        _select(window.app_language_combo, other)
        assert mock_settings.get("app_language") == other
        assert signals["language_change_requested"] == [(other,)]

    def test_injection_method_choice_is_saved(self, window, mock_settings):
        _select(window.injection_combo, "keystroke")
        assert mock_settings.get("injection_method") == "keystroke"

    def test_user_guide_button_asks_for_help(self, window, signals):
        _button(window, "settings.user_guide").click()
        assert signals["help_requested"] == [()]

    def test_quit_is_offered_only_when_there_is_no_tray(self, window):
        assert window.btn_quit.isHidden()
        window.set_tray_available(False)
        assert not window.btn_quit.isHidden()
        window.rebuild()
        assert not window.btn_quit.isHidden()
        window.set_tray_available(True)
        assert window.btn_quit.isHidden()


class TestMicrophone:
    def test_lists_the_microphones_and_reports_the_default(self, window, signals):
        window.populate_devices(MICS)
        assert [window.mic_combo.itemText(i) for i in range(2)] == ["USB Mic (Default)", "Headset"]
        assert window.mic_combo.currentData() == 3
        assert signals["device_changed"] == [(3,)]

    def test_the_saved_microphone_wins_over_the_default(self, window, mock_settings, signals):
        mock_settings.set_many({"device_index": 5, "device_name": "Headset"})
        window.populate_devices(MICS)
        assert window.mic_combo.currentData() == 5
        assert signals["device_changed"] == [(5,)]

    def test_the_saved_name_wins_when_the_index_moved(self, window, mock_settings):
        """Device indexes change when hardware is plugged in; the name is what the user chose."""
        mock_settings.set_many({"device_index": 5, "device_name": "Headset"})
        window.populate_devices([("USB Mic (Default)", 3, True), ("Headset", 9, False)])
        assert window.mic_combo.currentData() == 9

    def test_the_first_microphone_is_used_when_none_is_default(self, window, signals):
        window.populate_devices([("A", 1, False), ("B", 2, False)])
        assert signals["device_changed"] == [(1,)]

    def test_listing_the_microphones_saves_nothing(self, window, mock_settings):
        window.populate_devices(MICS)
        assert mock_settings.get("device_index") is None
        assert mock_settings.get("device_name") == ""

    def test_the_same_list_again_changes_nothing(self, window, signals):
        window.populate_devices(MICS)
        window.populate_devices(list(MICS))
        assert signals["device_changed"] == [(3,)]

    def test_line_breaks_in_driver_names_are_removed(self, window):
        window.populate_devices([("Headset\r\n(Hands-Free)", 7, False)])
        assert window.mic_combo.itemText(0) == "Headset (Hands-Free)"

    def test_no_microphone_disables_the_list_and_logs_a_warning(self, window, signals):
        window.populate_devices([])
        assert not window.mic_combo.isEnabled()
        assert window.mic_combo.count() == 0
        assert "No microphone found." in window.log_box.toPlainText()
        assert "device_changed" not in signals

    def test_microphones_coming_back_enable_the_list_again(self, window):
        window.populate_devices([])
        window.populate_devices(MICS)
        assert window.mic_combo.isEnabled()

    def test_picking_a_microphone_locks_it(self, window, mock_settings, signals):
        window.populate_devices(MICS)
        _select(window.mic_combo, 5)
        assert (mock_settings.get("device_index"), mock_settings.get("device_name")) == (5, "Headset")
        assert signals["device_changed"][-1] == (5,)

    def test_picking_the_default_entry_follows_the_system_default(self, window, mock_settings, signals):
        """ADR-0005: choosing the entry marked "(Default)" removes the lock."""
        mock_settings.set_many({"device_index": 5, "device_name": "Headset"})
        window.populate_devices(MICS)
        _select(window.mic_combo, 3)
        assert (mock_settings.get("device_index"), mock_settings.get("device_name")) == (-1, "")
        assert signals["device_changed"][-1] == (3,)

    @pytest.mark.parametrize("level, percent", [(0.0, 0), (0.42, 42), (1.0, 100), (3.0, 100), (-1.0, 0)])
    def test_level_bar_shows_the_level(self, window, level, percent):
        window.update_level(level)
        assert window.level_bar.value() == percent

    def test_level_bar_colour_follows_the_level(self, window):
        from ui.theme import theme_manager
        p = theme_manager.palette
        for level, colour in ((0.1, "CLR_INFO"), (0.3, "CLR_OK"), (0.6, "CLR_WARN"), (0.9, "CLR_ERR")):
            window.update_level(level)
            assert p[colour] in window.level_bar.styleSheet()


class TestLastRecording:
    """AudioWorker.recording_analysed, shown under the microphone."""

    def test_nothing_is_shown_before_the_first_recording(self, window):
        assert window.lbl_recording.text() == ""

    def test_shows_how_long_and_how_loud_it_was(self, window):
        window.show_last_recording(4.04, -47.6, -71.5, "")
        assert window.lbl_recording.text() == "Last recording: 4.0 s<br>speech -48 dB · noise -72 dB"

    def test_says_why_a_recording_was_dropped(self, window):
        window.show_last_recording(5.3, -56.7, -71.5, "osd.audio_too_quiet")
        assert "Signal level too low" in window.lbl_recording.text()

    def test_no_reason_is_shown_for_a_recording_that_went_on(self, window):
        window.show_last_recording(5.3, -56.7, -71.5, "osd.audio_too_quiet")
        window.show_last_recording(4.0, -40.0, -71.5, "")
        assert "Signal level too low" not in window.lbl_recording.text()

    def test_follows_the_language(self, window):
        from core.i18n import set_language
        window.show_last_recording(0.3, -60.0, -70.0, "osd.recording_too_short")
        set_language("tr")
        window.rebuild()
        assert "Son kayıt: 0.3 sn" in window.lbl_recording.text()
        assert "Kayıt çok kısa" in window.lbl_recording.text()


class TestModelInfo:
    """TranscriptionWorker.model_loaded and dictation_timed, shown under the model list."""

    def test_says_when_the_model_runs_on_the_gpu(self, window):
        window.on_model_loaded("cuda", "float16", "")
        assert window.lbl_model_info.text() == "GPU · float16"

    def test_says_why_the_model_is_on_the_cpu(self, window):
        window.on_model_loaded("cpu", "int8", "no NVIDIA GPU detected")
        assert window.lbl_model_info.text() == "CPU · int8 · no NVIDIA GPU detected"

    def test_shows_how_long_the_last_dictation_took(self, window):
        window.on_model_loaded("cuda", "float16", "")
        window.show_last_dictation(10.1, 0.62)
        assert "Last dictation: 10.1 s → 0.6 s" in window.lbl_model_info.text()

    def test_a_newly_loaded_model_forgets_the_old_timing(self, window):
        window.on_model_loaded("cuda", "float16", "")
        window.show_last_dictation(10.1, 0.62)
        window.on_model_loaded("cpu", "int8", "GPU could not run the model")
        assert "Last dictation" not in window.lbl_model_info.text()

    def test_hovering_shows_the_folder_of_the_model_in_use(self, window, models_root):
        medium = _make_model(models_root / "faster-whisper-medium")
        window.on_model_loaded("cpu", "int8", "")
        assert Path(window.lbl_model_info.toolTip()) == medium.resolve()


def _rows(window) -> dict:
    """Row text by what the row stands for (a repository id, or the browse / custom entry)."""
    combo = window.model_combo
    return {combo.itemData(i): combo.itemText(i) for i in range(combo.count())}


def _pick_to_download(window, repo: str, answer=QMessageBox.StandardButton.Yes) -> None:
    """The user picks a model that is not installed and answers the question that follows."""
    with patch.object(QMessageBox, "question", return_value=answer):
        _select(window.model_combo, repo)


class TestModelList:
    """One list with one job: closed, it names the model in use. Every row says its state, and
    for a model that is not installed that state is what picking the row does."""

    def test_each_row_says_its_state(self, window, mock_settings, models_root):
        small = _make_model(models_root / "faster-whisper-small")
        _make_model(models_root / "faster-whisper-medium")
        mock_settings.set("model_dir", str(small))
        window.show()
        rows = _rows(window)
        assert rows["Systran/faster-whisper-small"] == "Small · in use"
        assert rows["Systran/faster-whisper-medium"] == "Medium · installed"
        assert rows["Systran/faster-whisper-tiny"] == "Tiny · download (78 MB)"

    def test_the_closed_list_shows_the_model_in_use(self, window, models_root):
        """The stored model_dir may be just the models folder; the provider knows what is loaded."""
        _make_model(models_root / "faster-whisper-medium")
        window.show()
        assert window.model_combo.currentText() == "Medium · in use"

    def test_without_a_model_the_list_asks_for_one(self, window):
        window.show()
        assert window.model_combo.currentIndex() == -1
        assert window.model_combo.placeholderText() == "Choose a model"

    def test_picking_an_installed_model_applies_it(self, window, mock_settings, models_root, signals):
        _make_model(models_root / "faster-whisper-small")  # the one in use
        medium = _make_model(models_root / "faster-whisper-medium")
        window.show()
        _select(window.model_combo, "Systran/faster-whisper-medium")
        assert mock_settings.get("model_dir") == str(medium)
        assert signals["model_dir_changed"] == [(str(medium),)]
        assert "download_model_requested" not in signals

    def test_picking_a_model_that_is_not_installed_asks_to_download_it(self, window, models_root, signals):
        window.show()
        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes) as question:
            _select(window.model_combo, "Systran/faster-whisper-medium")
        assert "Medium" in question.call_args.args[2]
        assert signals["download_model_requested"] == [(str(models_root), "Systran/faster-whisper-medium")]
        assert "model_dir_changed" not in signals

    def test_declining_the_download_changes_nothing(self, window, models_root, signals):
        _make_model(models_root / "faster-whisper-small")
        window.show()
        _pick_to_download(window, "Systran/faster-whisper-medium", QMessageBox.StandardButton.No)
        assert "download_model_requested" not in signals
        assert window.model_combo.currentText() == "Small · in use"
        assert _rows(window)["Systran/faster-whisper-medium"] == "Medium · download (1.5 GB)"

    def test_the_list_stays_on_the_model_in_use_while_another_downloads(self, window, models_root):
        _make_model(models_root / "faster-whisper-small")
        window.show()
        _pick_to_download(window, "Systran/faster-whisper-medium")
        assert window.model_combo.currentText() == "Small · in use"
        assert _rows(window)["Systran/faster-whisper-medium"] == "Medium · downloading"

    def test_a_second_download_is_not_offered_while_one_runs(self, window, signals):
        window.show()
        _pick_to_download(window, "Systran/faster-whisper-medium")
        with patch.object(QMessageBox, "question") as question:
            _select(window.model_combo, "Systran/faster-whisper-tiny")
        question.assert_not_called()
        assert len(signals["download_model_requested"]) == 1
        assert window.model_combo.currentIndex() == -1   # still no model in use

    def test_a_download_that_ends_frees_its_row(self, window):
        """Finished or failed: the worker reports the end either way."""
        window.show()
        _pick_to_download(window, "Systran/faster-whisper-medium")
        window.set_download_state(True)
        window.set_download_state(False)
        assert _rows(window)["Systran/faster-whisper-medium"] == "Medium · download (1.5 GB)"

    def test_the_bar_shows_while_a_download_runs(self, window):
        window.show()
        window.set_download_state(True)
        assert not window.loading_bar.isHidden()
        window.set_download_state(False)
        assert window.loading_bar.isHidden()

    def test_the_download_is_named_before_its_size_is_known(self, window):
        window.show()
        _pick_to_download(window, "Systran/faster-whisper-medium")
        window.set_download_state(True)
        assert window.lbl_model_info.text() == "Medium · downloading"
        assert window.loading_bar.maximum() == 0      # sliding

    def test_download_progress_fills_the_bar_and_says_which_model_how_much_and_how_fast(self, window):
        window.show()
        _pick_to_download(window, "Systran/faster-whisper-large-v3")
        window.set_download_state(True)
        window.show_download_progress(3_090_839_273 / 2, 3.09e9, 6.1e6)
        assert window.loading_bar.value() * 2 == window.loading_bar.maximum()
        assert window.lbl_model_info.text() == "Large-v3 · downloading · 1.5 / 3.1 GB · 6.1 MB/s"

    def test_a_small_model_is_counted_in_megabytes(self, window):
        window.show()
        _pick_to_download(window, "Systran/faster-whisper-tiny")
        window.set_download_state(True)
        window.show_download_progress(32e6, 75e6, 5.8e6)
        assert "32 / 78 MB · 5.8 MB/s" in window.lbl_model_info.text()

    def test_the_total_is_the_size_the_row_promised(self, window):
        """The library learns the total file by file and leaves the small text files out: it
        says 76 MB for the tiny model, whose download is 78 MB."""
        window.show()
        assert _rows(window)["Systran/faster-whisper-tiny"] == "Tiny · download (78 MB)"
        _pick_to_download(window, "Systran/faster-whisper-tiny")
        window.set_download_state(True)
        window.show_download_progress(78_207_087 / 2, 2e6, 5.8e6)   # early: one small file known
        assert window.loading_bar.value() * 2 == window.loading_bar.maximum()
        assert "39 / 78 MB" in window.lbl_model_info.text()

    def test_progress_never_runs_past_the_end(self, window):
        """A repository that grew since its size was recorded must not overfill the bar."""
        window.show()
        _pick_to_download(window, "Systran/faster-whisper-tiny")
        window.set_download_state(True)
        window.show_download_progress(79e6, 76e6, 5.8e6)
        assert window.loading_bar.value() == window.loading_bar.maximum()
        assert "78 / 78 MB" in window.lbl_model_info.text()

    def test_progress_of_unknown_size_keeps_the_bar_sliding(self, window):
        """A download this window did not ask for has no row to take the size from."""
        window.show()
        window.set_download_state(True)
        window.show_download_progress(5e6, 0, 5.8e6)
        assert window.loading_bar.maximum() == 0
        assert "MB/s" not in window.lbl_model_info.text()

    def test_a_finished_download_takes_its_line_away(self, window):
        window.show()
        _pick_to_download(window, "Systran/faster-whisper-large-v3")
        window.set_download_state(True)
        window.show_download_progress(1.5e9, 3.09e9, 6.1e6)
        window.set_download_state(False)
        assert window.loading_bar.maximum() == 0      # sliding again for the next model load
        assert window.lbl_model_info.text() == ""

    def test_the_download_line_comes_before_the_facts_of_the_model_in_use(self, window):
        """Right under the bar stands what the bar is about. A GPU note of the model in use must
        not read as the reason a download failed."""
        window.show()
        window.on_model_loaded("cpu", "int8", "GPU load failed")
        _pick_to_download(window, "Systran/faster-whisper-medium")
        window.set_download_state(True)
        window.show_download_progress(0.4e9, 1.53e9, 6.1e6)
        first, second = window.lbl_model_info.text().split("<br>")
        assert first == "Medium · downloading · 0.4 / 1.5 GB · 6.1 MB/s"
        assert second == "CPU · int8 · GPU load failed"

    def test_loading_indicator_follows_the_model_load(self, window):
        assert window.loading_bar.isHidden()
        window.set_loading_indicator(True)
        assert not window.loading_bar.isHidden()
        window.set_loading_indicator(False)
        assert window.loading_bar.isHidden()

    def test_a_finished_download_becomes_the_model_in_use(self, window, mock_settings, models_root, signals):
        """It must still be the model after a restart, so the setting is written too."""
        medium = _make_model(models_root / "faster-whisper-medium")
        window.show()
        window.on_download_complete(str(medium))
        assert mock_settings.get("model_dir") == str(medium)
        assert window.model_combo.currentData() == "Systran/faster-whisper-medium"
        assert signals["model_dir_changed"] == [(str(medium),)]

    def test_browsing_to_a_model_folder_selects_it(self, window, mock_settings, tmp_path, signals):
        custom = _make_model(tmp_path / "elsewhere" / "my-model")
        window.show()
        # main.py tells the provider which model is in use as soon as the folder changes.
        window.model_dir_changed.connect(lambda path: setattr(window.model_provider, "active_model_path", path))
        with patch("ui.settings_window.QFileDialog.getExistingDirectory", return_value=str(custom)):
            _select(window.model_combo, "browse_custom")
        assert mock_settings.get("model_dir") == str(custom)
        assert signals["model_dir_changed"] == [(str(custom),)]
        assert window.model_combo.currentText() == "Custom: my-model · in use"

    def test_browsing_twice_to_the_same_folder_adds_one_entry(self, window, tmp_path):
        custom = _make_model(tmp_path / "elsewhere" / "my-model")
        window.show()
        before = window.model_combo.count()
        for _ in range(2):
            with patch("ui.settings_window.QFileDialog.getExistingDirectory", return_value=str(custom)):
                _select(window.model_combo, "browse_custom")
        assert window.model_combo.count() == before + 1

    def test_cancelling_the_browse_dialog_returns_to_the_previous_model(self, window, signals):
        window.show()
        previous = window.model_combo.currentData()
        with patch("ui.settings_window.QFileDialog.getExistingDirectory", return_value=""):
            _select(window.model_combo, "browse_custom")
        assert window.model_combo.currentData() == previous
        assert "model_dir_changed" not in signals

    def test_a_folder_without_a_model_is_refused(self, window, mock_settings, tmp_path, signals):
        window.show()
        previous = window.model_combo.currentData()
        with patch("ui.settings_window.QFileDialog.getExistingDirectory", return_value=str(tmp_path)), \
             patch.object(QMessageBox, "warning") as warning:
            _select(window.model_combo, "browse_custom")
        warning.assert_called_once()
        assert window.model_combo.currentData() == previous
        assert "model_dir_changed" not in signals

    def test_missing_model_opens_the_window_where_one_can_be_chosen(self, window):
        window.show_tab("log")
        window.show_model_missing_guidance()
        assert window.isVisible()
        assert window.tabs.currentIndex() == TABS.index("dictation")
        assert "No model found." in window.log_box.toPlainText()


class TestSpeechLanguageAndPrompt:
    def test_speech_language_choice_is_saved(self, window, mock_settings):
        _select(window.speech_language_combo, "tr")
        assert mock_settings.get("language") == "tr"

    def test_a_speech_language_brings_its_stock_prompt(self, window, mock_settings):
        _select(window.speech_language_combo, "tr")
        assert window.prompt_edit.toPlainText().startswith("Merhaba.")
        assert mock_settings.get("initial_prompt") == window.prompt_edit.toPlainText()

    def test_the_first_run_language_and_prompt_are_what_the_window_shows(self, window, mock_settings):
        """main.py stores them without the window (plan 0012 Faz 5); opening it must not change them."""
        from core.settings import first_run_speech_settings
        mock_settings.set_many(first_run_speech_settings("tr"))
        window.show()
        assert window.speech_language_combo.currentData() == "tr"
        assert window.prompt_edit.toPlainText() == mock_settings.get("initial_prompt")
        assert mock_settings.get("initial_prompt").startswith("Merhaba.")

    def test_automatic_detection_uses_no_prompt(self, window, mock_settings):
        _select(window.speech_language_combo, "tr")
        _select(window.speech_language_combo, "auto")
        assert window.prompt_edit.toPlainText() == ""
        assert mock_settings.get("initial_prompt") == ""

    def test_save_button_is_offered_only_for_an_unsaved_prompt(self, window):
        assert not window.btn_save_prompt.isEnabled()
        window.prompt_edit.setPlainText("This is technical documentation.")
        assert window.btn_save_prompt.isEnabled()
        window.btn_save_prompt.click()
        assert not window.btn_save_prompt.isEnabled()

    def test_a_saved_prompt_is_remembered_for_its_language(self, window, mock_settings):
        _select(window.speech_language_combo, "tr")
        window.prompt_edit.setPlainText("Bu teknik bir belgedir.")
        window.btn_save_prompt.click()
        _select(window.speech_language_combo, "en")
        _select(window.speech_language_combo, "tr")
        assert window.prompt_edit.toPlainText() == "Bu teknik bir belgedir."
        assert mock_settings.get("initial_prompt") == "Bu teknik bir belgedir."

    def test_a_prompt_saved_during_automatic_detection_is_not_filed_under_a_language(self, window, mock_settings):
        """The old dialog wrote it under the key None, which reached settings.json as "null"."""
        window.prompt_edit.setPlainText("Use lowercase only.")
        window.btn_save_prompt.click()
        assert mock_settings.get("initial_prompt") == "Use lowercase only."
        assert not mock_settings.get("initial_prompts")


class TestLogTab:
    def test_an_entry_shows_its_time_tag_component_and_message(self, window):
        window.append_log_entry("OK", "MIC", "Recording started")
        text = window.log_box.toPlainText()
        assert "OK" in text and "MIC" in text and "Recording started" in text
        assert text.startswith("[") and text[9] == "]"

    def test_in_progress_entries_are_shown_as_info(self, window):
        window.append_log_entry("...", "STT", "Loading")
        assert "INFO" in window.log_box.toPlainText()

    @pytest.mark.parametrize("level, colour", [
        ("OK", "CLR_OK"), ("ERR", "CLR_ERR"), ("WRN", "CLR_WARN"), ("...", "CLR_INFO"),
    ])
    def test_the_tag_takes_the_colour_of_its_level(self, window, level, colour):
        from ui.theme import theme_manager
        window.append_log_entry(level, "STT", "message")
        assert theme_manager.palette[colour].lower() in window.log_box.toHtml().lower()

    def test_markup_in_a_message_is_shown_as_text(self, window):
        window.append_log_entry("OK", "STT", "Transcript: '<b>bold</b>'")
        assert "<b>bold</b>" in window.log_box.toPlainText()

    def test_only_the_newest_entries_are_kept(self, window):
        for i in range(LOG_LIMIT + 20):
            window.append_log_entry("OK", "STT", f"entry {i}")
        window.rebuild()
        text = window.log_box.toPlainText()
        assert "entry 19" not in text.split("\n")[0]
        assert f"entry {LOG_LIMIT + 19}" in text
        assert len([line for line in text.split("\n") if line.strip()]) == LOG_LIMIT

    def test_translated_entries_follow_the_language(self, window):
        from core.i18n import set_language
        window.populate_devices([])
        set_language("tr")
        window.rebuild()
        assert "Mikrofon bulunamadı." in window.log_box.toPlainText()

    def test_open_log_folder_opens_it_in_explorer(self, window):
        from core.settings import get_log_dir
        with patch("os.path.exists", return_value=True), patch("os.startfile", create=True) as startfile:
            _button(window, "settings.open_log_folder").click()
        startfile.assert_called_once_with(str(get_log_dir()))

    def test_open_log_folder_warns_when_there_is_none_yet(self, window):
        logs = []
        on_log_entry(lambda level, component, message: logs.append((level, message)))
        with patch("os.path.exists", return_value=False), patch("os.startfile", create=True) as startfile:
            _button(window, "settings.open_log_folder").click()
        startfile.assert_not_called()
        assert logs == [("WRN", "Log folder has not been created yet.")]
