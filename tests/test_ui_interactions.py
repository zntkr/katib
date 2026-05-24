"""
User Interface (UI) interaction tests written using pure PySide6.
Simulates button clicks, theme changes, and user confirmation boxes (QMessageBox)
in the Dashboard and Settings dialogs.
"""
import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from ui.dashboard import DashboardWindow
from ui.utils import _make_icon


@pytest.fixture
def dashboard(qapp, mock_settings):
    w = DashboardWindow(mock_settings, icon_idle=_make_icon("#ffffff"))
    return w


class TestDashboardMethods:

    # ── __init__ DWM exception handler ──────────────────────────────────────

    def test_init_survives_dark_mode_error(self, qapp, mock_settings):
        from ui.utils import _make_icon
        with patch("ui.dashboard.apply_dark_mode_to_window", side_effect=Exception("no dwm")):
            w = DashboardWindow(mock_settings, icon_idle=_make_icon("#ffffff"))
        assert w is not None

    # ── _on_audio_inputs_changed ─────────────────────────────────────────────

    def test_audio_inputs_changed_emits_refresh(self, dashboard):
        from PySide6.QtTest import QSignalSpy
        spy = QSignalSpy(dashboard.refresh_devices_requested)
        dashboard._on_audio_inputs_changed()
        assert spy.count() == 1

    # ── setup_icon_button fallback (no SVG) ──────────────────────────────────

    def test_icon_button_fallback_text_when_no_svg(self, qapp, mock_settings):
        with patch("os.path.exists", return_value=False):
            from ui.utils import _make_icon
            w = DashboardWindow(mock_settings, icon_idle=_make_icon("#ffffff"))
        assert w is not None

    # ── _toggle_logs ─────────────────────────────────────────────────────────

    def test_toggle_logs_shows_log_widget(self, dashboard):
        assert dashboard.log_widget.isHidden()
        dashboard._toggle_logs()
        assert not dashboard.log_widget.isHidden()

    def test_toggle_logs_hides_log_widget(self, dashboard, qapp):
        dashboard.show()
        qapp.processEvents()
        dashboard._toggle_logs()  # show
        dashboard._toggle_logs()  # hide
        assert dashboard.log_widget.isHidden()
        dashboard.hide()

    # ── _populate_devices ────────────────────────────────────────────────────

    def test_populate_devices_emits_signal(self, dashboard):
        from PySide6.QtTest import QSignalSpy
        spy = QSignalSpy(dashboard.refresh_devices_requested)
        dashboard._populate_devices()
        assert spy.count() == 1

    # ── populate_devices ─────────────────────────────────────────────────────

    def test_populate_devices_fills_combo(self, dashboard):
        items = [("Mic 1", 0, True), ("Mic 2", 1, False)]
        dashboard.populate_devices(items)
        assert dashboard.mic_combo.count() == 2

    def test_populate_devices_skips_duplicate_list(self, dashboard):
        items = [("Mic 1", 0, True)]
        dashboard.populate_devices(items)
        dashboard.populate_devices(items)
        assert dashboard.mic_combo.count() == 1

    def test_populate_devices_selects_saved_device(self, dashboard, mock_settings):
        mock_settings.set("device_index", 1)
        dashboard.populate_devices([("Mic A", 0, True), ("Mic B", 1, False)])
        assert dashboard.mic_combo.currentData() == 1

    def test_populate_devices_empty_emits_warning(self, dashboard):
        logs = []
        dashboard.append_log_entry = lambda l, c, m, k="": logs.append(l)
        dashboard.populate_devices([])
        assert "WRN" in logs

    # ── _position_bottom_right ───────────────────────────────────────────────

    def test_position_bottom_right_runs(self, dashboard, qapp):
        with patch("ui.utils_win.get_dwm_visual_bounds", return_value=None):
            dashboard._position_bottom_right()

    def test_position_bottom_right_with_dwm_bounds(self, dashboard, qapp):
        with patch("ui.utils_win.get_dwm_visual_bounds", return_value=(0, 0, 330, 200)):
            dashboard._position_bottom_right()

    # ── showEvent ────────────────────────────────────────────────────────────

    def test_show_event_runs(self, dashboard, qapp):
        from PySide6.QtGui import QShowEvent
        from PySide6.QtCore import QEvent
        event = QShowEvent()
        dashboard.showEvent(event)

    # ── paintEvent ───────────────────────────────────────────────────────────

    def test_paint_event_runs(self, dashboard, qapp):
        dashboard.show()
        qapp.processEvents()
        dashboard.hide()

    # ── _on_device_changed ────────────────────────────────────────────────────

    def test_device_changed_saves_and_emits(self, dashboard, mock_settings):
        from PySide6.QtTest import QSignalSpy
        spy = QSignalSpy(dashboard.device_changed)
        dashboard.populate_devices([("Mic A", 0, True), ("Mic B", 3, False)])
        dashboard.mic_combo.setCurrentIndex(1)
        assert mock_settings.get("device_index") == 3
        assert spy.count() >= 1

    def test_device_changed_none_data_is_noop(self, dashboard):
        dashboard.mic_combo.blockSignals(True)
        dashboard.mic_combo.addItem("No data", userData=None)
        dashboard.mic_combo.setCurrentIndex(dashboard.mic_combo.count() - 1)
        dashboard.mic_combo.blockSignals(False)
        dashboard._on_device_changed(dashboard.mic_combo.currentIndex())

    # ── set_loading_indicator ─────────────────────────────────────────────────

    def test_set_loading_indicator_active_sets_indeterminate(self, dashboard):
        dashboard.set_loading_indicator(True)
        assert dashboard.level_bar.maximum() == 0

    def test_set_loading_indicator_inactive_restores_range(self, dashboard):
        dashboard.set_loading_indicator(True)
        dashboard.set_loading_indicator(False)
        assert dashboard.level_bar.maximum() == 100

    # ── append_log_entry ─────────────────────────────────────────────────────

    def test_append_log_entry_ok(self, dashboard):
        dashboard.append_log_entry("OK", "TST", "test message")

    def test_append_log_entry_err(self, dashboard):
        dashboard.append_log_entry("ERR", "TST", "error")

    def test_append_log_entry_wrn(self, dashboard):
        dashboard.append_log_entry("WRN", "TST", "warning")

    def test_append_log_entry_idle(self, dashboard):
        dashboard.append_log_entry("...", "TST", "loading")

    def test_append_log_entry_info(self, dashboard):
        dashboard.append_log_entry("INFO", "TST", "info")

    def test_append_log_entry_escapes_html(self, dashboard):
        dashboard.append_log_entry("OK", "TST", "<script>alert(1)</script>")

    # ── update_level ─────────────────────────────────────────────────────────

    def test_update_level_low(self, dashboard):
        from core.settings import STATE_LISTENING
        dashboard.set_status(STATE_LISTENING)
        dashboard.set_loading_indicator(False)
        dashboard.update_level(0.3)
        assert dashboard.level_bar.value() == 30

    def test_update_level_mid(self, dashboard):
        dashboard.set_loading_indicator(False)
        dashboard.update_level(0.7)

    def test_update_level_high(self, dashboard):
        dashboard.set_loading_indicator(False)
        dashboard.update_level(0.95)

    def test_update_level_skipped_in_loading_mode(self, dashboard):
        dashboard.set_loading_indicator(True)
        dashboard.update_level(0.9)
        assert dashboard.level_bar.maximum() == 0

    def test_update_level_same_color_skips_stylesheet(self, dashboard):
        dashboard.set_loading_indicator(False)
        dashboard.update_level(0.3)
        dashboard._last_level_color = dashboard._last_level_color
        dashboard.update_level(0.3)  # same color, no stylesheet update

    # ── set_status ───────────────────────────────────────────────────────────

    def test_set_status_ok(self, dashboard):
        from core.settings import STATE_READY
        from core.i18n import t
        dashboard.set_status(STATE_READY, "OK")
        assert t(STATE_READY) in dashboard.status_label.text()

    def test_set_status_err(self, dashboard):
        dashboard.set_status("Error", "ERR")

    def test_set_status_unknown_level(self, dashboard):
        dashboard.set_status("Unknown", "XYZ")

    # ── show_model_missing_guidance ───────────────────────────────────────────

    def test_model_missing_guidance_opens_log_panel(self, dashboard):
        assert dashboard.log_widget.isHidden()
        dashboard.show_model_missing_guidance()
        assert not dashboard.log_widget.isHidden()

    def test_model_missing_guidance_appends_info_log(self, dashboard):
        dashboard.show_model_missing_guidance()
        html = dashboard.log_box.toHtml()
        assert "No model found" in html

    def test_model_missing_guidance_makes_status_label_clickable(self, dashboard):
        assert not dashboard._status_clickable
        dashboard.show_model_missing_guidance()
        assert dashboard._status_clickable

    def test_model_missing_guidance_does_not_close_open_log_panel(self, dashboard):
        dashboard._toggle_logs()  # open first
        assert not dashboard.log_widget.isHidden()
        dashboard.show_model_missing_guidance()
        assert not dashboard.log_widget.isHidden()  # still open

    def test_clear_model_missing_guidance_removes_clickable(self, dashboard):
        dashboard.show_model_missing_guidance()
        dashboard.clear_model_missing_guidance()
        assert not dashboard._status_clickable

    def test_status_label_click_after_guidance_opens_settings(self, dashboard):
        dashboard.show_model_missing_guidance()
        with patch.object(dashboard, "_open_settings_dialog") as mock_open:
            from PySide6.QtGui import QMouseEvent
            from PySide6.QtCore import QEvent, QPointF
            event = QMouseEvent(
                QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            dashboard._on_status_label_click(event)
        mock_open.assert_called_once()

    def test_status_label_click_after_clear_does_not_open_settings(self, dashboard):
        dashboard.show_model_missing_guidance()
        dashboard.clear_model_missing_guidance()
        with patch.object(dashboard, "_open_settings_dialog") as mock_open:
            from PySide6.QtGui import QMouseEvent
            from PySide6.QtCore import QEvent, QPointF
            event = QMouseEvent(
                QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            dashboard._on_status_label_click(event)
        mock_open.assert_not_called()

    # ── keyPressEvent ─────────────────────────────────────────────────────────

    def test_keypressevent_escape_hides(self, dashboard):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        dashboard.show()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        dashboard.keyPressEvent(event)
        assert not dashboard.isVisible()

    def test_keypressevent_other_key_does_not_hide(self, dashboard):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        dashboard.keyPressEvent(event)

    # ── selected_device_index ─────────────────────────────────────────────────

    def test_selected_device_index_returns_current_data(self, dashboard):
        dashboard.populate_devices([("Mic", 5, True)])
        assert dashboard.selected_device_index() == 5

    # ── set_download_state ────────────────────────────────────────────────────

    def test_set_download_state_no_dialog(self, dashboard):
        dashboard.set_download_state(True)
        assert dashboard.level_bar.maximum() == 0

    def test_set_download_state_with_dialog(self, dashboard, mock_settings):
        dashboard._open_settings_dialog()
        dashboard.set_download_state(True)
        assert not dashboard._settings_dialog.btn_download.isEnabled()

    # ── on_download_complete ──────────────────────────────────────────────────

    def test_on_download_complete_no_dialog_emits_signal(self, dashboard):
        from PySide6.QtTest import QSignalSpy
        spy = QSignalSpy(dashboard.model_dir_changed)
        dashboard.on_download_complete("/some/path")
        assert spy.count() == 1

    def test_on_download_complete_with_dialog(self, dashboard, tmp_path):
        dashboard._open_settings_dialog()
        dashboard.on_download_complete(str(tmp_path))
        assert str(tmp_path) in dashboard._settings_dialog.lbl_model_path.toolTip()

    # ── show_help ─────────────────────────────────────────────────────────────

    def test_show_help_creates_window(self, dashboard):
        dashboard.show_help()
        assert dashboard._help_window is not None

    def test_show_help_reuses_window(self, dashboard):
        dashboard.show_help()
        w1 = dashboard._help_window
        dashboard.show_help()
        assert dashboard._help_window is w1

    # ── _open_settings_dialog overflow ───────────────────────────────────────

    def test_open_settings_dialog_overflow_x(self, dashboard):
        with patch.object(dashboard, "frameGeometry") as mock_geo:
            mock_geo.return_value.x.return_value = 0
            mock_geo.return_value.y.return_value = 100
            mock_geo.return_value.width.return_value = 320
            mock_geo.return_value.height.return_value = 200
            dashboard._open_settings_dialog()

    # ── _on_hotkey_from_dialog ────────────────────────────────────────────────

    def test_on_hotkey_from_dialog_emits_signal(self, dashboard):
        from PySide6.QtTest import QSignalSpy
        spy = QSignalSpy(dashboard.hotkey_changed)
        dashboard._on_hotkey_from_dialog("f10")
        assert spy.count() == 1
        assert spy.at(0)[0] == "f10"


class TestDashboardUIInteractions:
    def test_open_settings_creates_dialog(self, dashboard):
        """Tests that clicking the Settings button opens the dialog window."""
        dashboard._open_settings_dialog()
        assert dashboard._settings_dialog is not None
        # isVisible() might be False in headless CI, but let's check if it's created
        assert dashboard._settings_dialog.windowTitle() != ""




@pytest.fixture
def settings_dialog(qapp, mock_settings):
    from ui.settings_dialog import SettingsDialog
    dlg = SettingsDialog(mock_settings)
    return dlg


class TestSettingsDialogInteractions:

    # ── wheelEvent ───────────────────────────────────────────────────────────

    def test_no_scroll_combo_ignores_wheel_event(self, settings_dialog):
        from PySide6.QtCore import QPoint, QPointF
        from PySide6.QtGui import QWheelEvent
        from PySide6.QtCore import Qt
        combo = settings_dialog.model_select_combo
        before = combo.currentIndex()
        event = QWheelEvent(
            QPointF(0, 0), QPointF(0, 0),
            QPoint(0, 120), QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False
        )
        combo.wheelEvent(event)
        assert combo.currentIndex() == before

    # ── paintEvent ───────────────────────────────────────────────────────────

    def test_paint_event_does_not_raise(self, settings_dialog):
        settings_dialog.repaint()

    # ── show() exception handler ─────────────────────────────────────────────

    def test_show_survives_dark_mode_error(self, settings_dialog):
        with patch("ui.settings_dialog.apply_dark_mode_to_window", side_effect=Exception("no dwm")):
            settings_dialog.show()
        settings_dialog.hide()


    # ── log folder ───────────────────────────────────────────────────────────

    def test_open_log_folder_when_missing_emits_warning(self, settings_dialog):
        logs = []
        settings_dialog.log_entry.connect(lambda l, c, m: logs.append(l))
        with patch("os.path.exists", return_value=False):
            settings_dialog._open_log_folder()
        assert "WRN" in logs

    def test_open_log_folder_when_exists_calls_startfile(self, settings_dialog):
        with patch("os.path.exists", return_value=True), \
             patch("os.startfile") as mock_sf:
            settings_dialog._open_log_folder()
        mock_sf.assert_called_once()

    # ── hotkey capture ───────────────────────────────────────────────────────

    def test_start_hotkey_capture_changes_button_text(self, settings_dialog):
        settings_dialog._start_hotkey_capture()
        assert settings_dialog.btn_hotkey.text() == "Press a key..."
        assert settings_dialog._capturing_hotkey is True

    def test_end_hotkey_capture_restores_button(self, settings_dialog):
        settings_dialog._start_hotkey_capture()
        settings_dialog._end_hotkey_capture("f10")
        assert settings_dialog.btn_hotkey.text() == "F10"
        assert settings_dialog._capturing_hotkey is False

    # ── keyPressEvent ────────────────────────────────────────────────────────

    def test_keypressevent_escape_hides_dialog(self, settings_dialog):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        settings_dialog.show()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        settings_dialog.keyPressEvent(event)
        assert not settings_dialog.isVisible()

    def test_keypressevent_captures_f10(self, settings_dialog, mock_settings):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        settings_dialog._start_hotkey_capture()
        with patch("ui.utils.qt_key_to_keyboard", return_value="f10"):
            event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F10, Qt.KeyboardModifier.NoModifier)
            settings_dialog.keyPressEvent(event)
        assert mock_settings.get("hotkey") == "f10"
        assert settings_dialog._capturing_hotkey is False

    def test_keypressevent_escape_during_capture_reverts(self, settings_dialog, mock_settings):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        mock_settings.set("hotkey", "f9")
        settings_dialog._start_hotkey_capture()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        settings_dialog.keyPressEvent(event)
        assert settings_dialog._capturing_hotkey is False
        assert settings_dialog.btn_hotkey.text() == "F9"

    def test_keypressevent_unknown_key_stays_capturing(self, settings_dialog):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        settings_dialog._start_hotkey_capture()
        with patch("ui.utils.qt_key_to_keyboard", return_value=None):
            event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.NoModifier)
            settings_dialog.keyPressEvent(event)
        assert settings_dialog._capturing_hotkey is True

    def test_keypressevent_with_ctrl_modifier(self, settings_dialog, mock_settings):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        settings_dialog._start_hotkey_capture()
        with patch("ui.utils.qt_key_to_keyboard", return_value="f1"):
            event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F1, Qt.KeyboardModifier.ControlModifier)
            settings_dialog.keyPressEvent(event)
        assert mock_settings.get("hotkey") == "ctrl+f1"

    # ── theme changed ─────────────────────────────────────────────────────────

    # ── combo index changed ──────────────────────────────────────────────────

    def test_combo_custom_item_does_not_save_repo(self, settings_dialog, mock_settings):
        custom_id = "custom:/some/path"
        combo = settings_dialog.model_select_combo
        combo.blockSignals(True)
        combo.insertItem(0, "Custom", userData=custom_id)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)
        mock_settings.set("selected_model_repo", "")
        settings_dialog._on_combo_index_changed(0)
        assert mock_settings.get("selected_model_repo") == ""

    def test_revert_combo_restores_last_index(self, settings_dialog):
        settings_dialog._last_combo_idx = 1
        settings_dialog.model_select_combo.blockSignals(True)
        settings_dialog.model_select_combo.setCurrentIndex(3)
        settings_dialog.model_select_combo.blockSignals(False)
        settings_dialog._revert_combo()
        assert settings_dialog.model_select_combo.currentIndex() == 1

    # ── browse model dir ─────────────────────────────────────────────────────

    def test_browse_model_dir_cancel_reverts_combo(self, settings_dialog):
        settings_dialog._last_combo_idx = 0
        with patch("ui.settings_dialog.QFileDialog.getExistingDirectory", return_value=""):
            settings_dialog._browse_model_dir()
        assert settings_dialog.model_select_combo.currentIndex() == 0

    def test_browse_model_dir_invalid_path_shows_warning(self, settings_dialog):
        with patch("ui.settings_dialog.QFileDialog.getExistingDirectory", return_value="/some/path"), \
             patch("ui.settings_dialog.validate_model_dir", return_value=None), \
             patch("ui.settings_dialog.QMessageBox.warning") as mock_warn:
            settings_dialog._browse_model_dir()
        mock_warn.assert_called_once()

    def test_browse_model_dir_valid_path_emits_signal(self, settings_dialog, tmp_path):
        from PySide6.QtTest import QSignalSpy
        spy = QSignalSpy(settings_dialog.model_dir_changed)
        with patch("ui.settings_dialog.QFileDialog.getExistingDirectory", return_value=str(tmp_path)), \
             patch("ui.settings_dialog.validate_model_dir", return_value=str(tmp_path)):
            settings_dialog._browse_model_dir()
        assert spy.count() == 1

    # ── sync combo with custom path ──────────────────────────────────────────

    def test_sync_combo_with_unrecognised_dir_adds_custom_item(self, settings_dialog):
        settings_dialog._sync_combo_with_current_dir("/some/custom/model-xyz")
        idx = settings_dialog.model_select_combo.findData("custom:/some/custom/model-xyz")
        assert idx >= 0

    def test_sync_combo_with_existing_custom_item_reuses_it(self, settings_dialog):
        settings_dialog._sync_combo_with_current_dir("/some/custom/model-xyz")
        count_before = settings_dialog.model_select_combo.count()
        settings_dialog._sync_combo_with_current_dir("/some/custom/model-xyz")
        assert settings_dialog.model_select_combo.count() == count_before

    # ── check selected model status guard ────────────────────────────────────

    def test_check_status_returns_early_for_browse_custom(self, settings_dialog):
        settings_dialog.model_select_combo.blockSignals(True)
        settings_dialog.model_select_combo.setCurrentIndex(
            settings_dialog.model_select_combo.findData("browse_custom")
        )
        settings_dialog.model_select_combo.blockSignals(False)
        settings_dialog._check_selected_model_status()  # should not raise

    # ── download clicked guards ──────────────────────────────────────────────

    def test_download_clicked_browse_custom_is_noop(self, settings_dialog):
        settings_dialog.model_select_combo.blockSignals(True)
        settings_dialog.model_select_combo.setCurrentIndex(
            settings_dialog.model_select_combo.findData("browse_custom")
        )
        settings_dialog.model_select_combo.blockSignals(False)
        settings_dialog._on_download_clicked()  # should not raise or emit

    def test_download_clicked_not_installed_no_reply_does_nothing(self, settings_dialog, mock_settings):
        with patch("ui.settings_dialog.validate_model_dir", return_value=None), \
             patch.object(settings_dialog, "_get_selected_model_path", return_value=MagicMock()), \
             patch("ui.settings_dialog.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No):
            settings_dialog._on_download_clicked()
        assert mock_settings.get("model_dir") != "/fake"

    # ── compute type ─────────────────────────────────────────────────────────

    def test_compute_type_changed_with_no_data_is_noop(self, settings_dialog):
        settings_dialog.compute_combo.clear()
        settings_dialog._on_compute_type_changed(0)  # should not raise

    def test_populate_compute_type_options_fills_combo(self, settings_dialog):
        settings_dialog._populate_compute_type_options()
        assert settings_dialog.compute_combo.count() > 0

    # ── refresh values ───────────────────────────────────────────────────────

    def test_refresh_values_syncs_all_widgets(self, settings_dialog, mock_settings):
        mock_settings.set("hotkey", "f5")
        mock_settings.set("beam_size", 3)
        settings_dialog._refresh_values()
        assert settings_dialog.btn_hotkey.text() == "F5"


    # ── set_download_state ───────────────────────────────────────────────────

    def test_set_download_state_active_disables_button(self, settings_dialog):
        settings_dialog.set_download_state(True)
        assert not settings_dialog.btn_download.isEnabled()

    def test_set_download_state_inactive_enables_button(self, settings_dialog):
        settings_dialog.set_download_state(True)
        settings_dialog.set_download_state(False)
        assert settings_dialog.btn_download.isEnabled()

    # ── on_download_complete ─────────────────────────────────────────────────

    def test_on_download_complete_updates_path_label(self, settings_dialog, tmp_path):
        settings_dialog.on_download_complete(str(tmp_path))
        assert str(tmp_path) in settings_dialog.lbl_model_path.toolTip()

    # ── paintEvent ───────────────────────────────────────────────────────────

    def test_paint_event_via_show(self, settings_dialog, qapp):
        from PySide6.QtGui import QPaintEvent
        from PySide6.QtCore import QRect
        settings_dialog.show()
        qapp.processEvents()
        settings_dialog.hide()

    def test_paint_event_via_update(self, settings_dialog, qapp):
        settings_dialog.show()
        settings_dialog.update()
        qapp.processEvents()
        settings_dialog.hide()

    # ── _on_dynamic_changed ──────────────────────────────────────────────────

    def test_dynamic_widget_change_saves_setting(self, settings_dialog, mock_settings):
        lang_widget = settings_dialog._dynamic_widgets.get("language")
        assert lang_widget is not None
        lang_widget.setCurrentIndex(0)
        assert mock_settings.get("language") is None  # "auto" → None conversion

    # ── badge "not installed" branch ─────────────────────────────────────────

    def test_refresh_badges_marks_uninstalled_models(self, settings_dialog):
        with patch("ui.settings_dialog.validate_model_dir", return_value=None):
            settings_dialog._refresh_model_combo_badges()
        text = settings_dialog.model_select_combo.itemText(0)
        assert text.startswith("  ")

    # ── download: Yes triggers emit ───────────────────────────────────────────

    def test_download_clicked_yes_emits_download_requested(self, settings_dialog):
        from PySide6.QtTest import QSignalSpy
        spy = QSignalSpy(settings_dialog.download_model_requested)
        with patch("ui.settings_dialog.validate_model_dir", return_value=None), \
             patch.object(settings_dialog, "_get_selected_model_path", return_value=MagicMock()), \
             patch("ui.settings_dialog.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes):
            settings_dialog._on_download_clicked()
        assert spy.count() == 1

    # ── compute type valid change ─────────────────────────────────────────────

    def test_compute_type_changed_saves_and_emits(self, settings_dialog, mock_settings):
        from PySide6.QtTest import QSignalSpy
        spy = QSignalSpy(settings_dialog.model_reload_requested)
        settings_dialog._populate_compute_type_options()
        settings_dialog.compute_combo.setCurrentIndex(1)
        assert spy.count() >= 1

    # ── _reset_advanced ───────────────────────────────────────────────────────

    def test_reset_advanced_emits_ok_log(self, settings_dialog, mock_settings):
        logs = []
        settings_dialog.log_entry.connect(lambda l, c, m: logs.append(l))
        settings_dialog._reset_advanced()
        assert "OK" in logs

    # ── keyPressEvent non-escape when not capturing ───────────────────────────

    def test_keypressevent_non_escape_when_not_capturing(self, settings_dialog):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        assert not settings_dialog._capturing_hotkey
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        settings_dialog.keyPressEvent(event)  # should not raise

    # ── apply_installed model (regression) ──────────────────────────────────
    def test_apply_installed_model_saves_model_dir(self, settings_dialog, mock_settings, tmp_path):
        """When a downloaded model is selected from the combo (Auto-Apply), model_dir should be written to settings."""
        fake_model_dir = str(tmp_path)
        with patch("ui.settings_dialog.validate_model_dir", return_value=fake_model_dir):
            with patch.object(settings_dialog, "_get_selected_model_path", return_value=tmp_path):
                settings_dialog.model_select_combo.blockSignals(True)
                settings_dialog.model_select_combo.addItem("Fake Model", userData="repo/fake")
                idx = settings_dialog.model_select_combo.count() - 1
                settings_dialog.model_select_combo.setCurrentIndex(idx)
                settings_dialog.model_select_combo.blockSignals(False)
                settings_dialog._on_combo_index_changed(idx)
        assert mock_settings.get("model_dir") == fake_model_dir

    def test_apply_installed_model_emits_model_dir_changed(self, settings_dialog, mock_settings, tmp_path):
        """When a downloaded model is selected from the combo (Auto-Apply), the model_dir_changed signal should be emitted."""
        from PySide6.QtTest import QSignalSpy
        fake_model_dir = str(tmp_path)
        spy = QSignalSpy(settings_dialog.model_dir_changed)
        with patch("ui.settings_dialog.validate_model_dir", return_value=fake_model_dir):
            with patch.object(settings_dialog, "_get_selected_model_path", return_value=tmp_path):
                settings_dialog.model_select_combo.blockSignals(True)
                settings_dialog.model_select_combo.addItem("Fake Model", userData="repo/fake")
                idx = settings_dialog.model_select_combo.count() - 1
                settings_dialog.model_select_combo.setCurrentIndex(idx)
                settings_dialog.model_select_combo.blockSignals(False)
                settings_dialog._on_combo_index_changed(idx)
        assert spy.count() == 1
        assert spy.at(0)[0] == fake_model_dir


# ── HelpWindow ────────────────────────────────────────────────────────────────

@pytest.fixture
def help_window(qapp):
    from ui.help_window import HelpWindow
    w = HelpWindow()
    yield w
    w.close()


class TestHelpWindow:

    def test_paint_event_does_not_crash(self, help_window, qapp):
        help_window.show()
        help_window.update()
        qapp.processEvents()
        help_window.hide()

    def test_show_does_not_crash(self, help_window, qapp):
        with patch("ui.help_window.apply_dark_mode_to_window"):
            help_window.show()
        qapp.processEvents()
        help_window.hide()

    def test_keypressevent_escape_closes_window(self, help_window, qapp):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        with patch("ui.help_window.apply_dark_mode_to_window"):
            help_window.show()
        qapp.processEvents()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        help_window.keyPressEvent(event)
        assert not help_window.isVisible()

    def test_keypressevent_non_escape_keeps_window_open(self, help_window, qapp):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        with patch("ui.help_window.apply_dark_mode_to_window"):
            help_window.show()
        qapp.processEvents()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        help_window.keyPressEvent(event)
        assert help_window.isVisible()
        help_window.hide()

    def test_show_dark_mode_exception_swallowed(self, help_window, qapp):
        """If apply_dark_mode_to_window raises an exception it should be silently swallowed (lines 190-191)."""
        with patch("ui.help_window.apply_dark_mode_to_window", side_effect=Exception("no dwm")):
            help_window.show()
        qapp.processEvents()
        help_window.hide()


class TestDashboardCoverage:
    def test_icon_button_setup_with_existing_svg(self, qapp, mock_settings):
        with patch("os.path.exists", return_value=True):
            from ui.utils import _make_icon
            w = DashboardWindow(mock_settings, icon_idle=_make_icon("#ffffff"))
        assert w is not None

    def test_finalize_position_in_showEvent(self, dashboard):
        from PySide6.QtGui import QShowEvent
        with patch("PySide6.QtCore.QTimer.singleShot") as mock_timer:
            dashboard.showEvent(QShowEvent())
            callback = mock_timer.call_args[0][1]
            callback()
        assert dashboard.windowOpacity() == 1.0

    def test_position_help_none(self, dashboard):
        dashboard._help_window = None
        dashboard._position_help_beside_dashboard()

    def test_position_settings_none(self, dashboard):
        dashboard._settings_dialog = None
        dashboard._position_settings_beside_dashboard()

    def test_position_bottom_right_with_bounds(self, dashboard):
        with patch("ui.utils_win.get_dwm_visual_bounds", return_value=(0, 0, 100, 100)):
            dashboard._position_bottom_right()

    def test_position_help_with_bounds(self, dashboard):
        dashboard.show_help()
        with patch("ui.utils_win.get_dwm_visual_bounds", return_value=(0, 0, 100, 100)):
            dashboard._position_help_beside_dashboard()

    def test_position_settings_with_bounds(self, dashboard):
        dashboard._open_settings_dialog()
        with patch("ui.utils_win.get_dwm_visual_bounds", return_value=(0, 0, 100, 100)):
            dashboard._position_settings_beside_dashboard()

    def test_position_help_x_less_than_left(self, dashboard):
        from PySide6.QtCore import QRect
        dashboard.show_help()
        with patch.object(dashboard, "frameGeometry", return_value=QRect(0, 0, 300, 300)), \
             patch("PySide6.QtWidgets.QApplication.primaryScreen") as mock_screen:
            mock_screen.return_value.availableGeometry.return_value = QRect(10000, 0, 1920, 1080)
            dashboard._position_help_beside_dashboard()

    def test_position_settings_x_less_than_left(self, dashboard):
        from PySide6.QtCore import QRect
        dashboard._open_settings_dialog()
        with patch.object(dashboard, "frameGeometry", return_value=QRect(0, 0, 300, 300)), \
             patch("PySide6.QtWidgets.QApplication.primaryScreen") as mock_screen:
            mock_screen.return_value.availableGeometry.return_value = QRect(10000, 0, 1920, 1080)
            dashboard._position_settings_beside_dashboard()
            
    def test_copy_transcript_tooltip_timer(self, dashboard):
        dashboard.set_last_transcript("test")
        with patch("PySide6.QtCore.QTimer.singleShot") as mock_timer:
            dashboard._copy_last_transcript()
            callback = mock_timer.call_args[0][1]
            callback()
        assert dashboard.btn_copy_transcript.toolTip() == "Copy last transcript"

    def test_toggle_logs_keeps_bottom_edge_fixed(self, dashboard):
        with patch.object(dashboard, "_position_bottom_right") as mock_pos, \
             patch.object(dashboard, "move") as mock_move:
            dashboard._toggle_logs()
            mock_pos.assert_not_called()
            mock_move.assert_called_once()
