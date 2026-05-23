"""
Qt UI bileşen testleri.
_qt_key_to_keyboard, DashboardWindow, log limiti vb.
QApplication fixture (conftest.py) gerektirir.
"""
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.modules['keyboard'] = MagicMock()
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt


def _make_icon():
    px = QPixmap(1, 1)
    px.fill(Qt.GlobalColor.transparent)
    return QIcon(px)


class TestQtKeyToKeyboard:
    """qt_key_to_keyboard() saf dönüşüm fonksiyonu testleri."""

    @pytest.fixture(autouse=True)
    def _import(self, qapp):
        from ui.utils import qt_key_to_keyboard
        self.fn = qt_key_to_keyboard

    def test_f1_through_f12(self):
        from PySide6.QtCore import Qt
        for i in range(1, 13):
            qt_key = getattr(Qt.Key, f"Key_F{i}")
            assert self.fn(qt_key) == f"f{i}"

    def test_space(self):
        from PySide6.QtCore import Qt
        assert self.fn(Qt.Key.Key_Space) == "space"

    def test_enter(self):
        from PySide6.QtCore import Qt
        assert self.fn(Qt.Key.Key_Return) == "enter"

    def test_escape(self):
        from PySide6.QtCore import Qt
        assert self.fn(Qt.Key.Key_Escape) == "esc"

    def test_tab(self):
        from PySide6.QtCore import Qt
        assert self.fn(Qt.Key.Key_Tab) == "tab"

    def test_backspace(self):
        from PySide6.QtCore import Qt
        assert self.fn(Qt.Key.Key_Backspace) == "backspace"

    def test_delete(self):
        from PySide6.QtCore import Qt
        assert self.fn(Qt.Key.Key_Delete) == "delete"

    def test_home(self):
        from PySide6.QtCore import Qt
        assert self.fn(Qt.Key.Key_Home) == "home"

    def test_end(self):
        from PySide6.QtCore import Qt
        assert self.fn(Qt.Key.Key_End) == "end"

    def test_arrow_keys(self):
        from PySide6.QtCore import Qt
        assert self.fn(Qt.Key.Key_Up)    == "up"
        assert self.fn(Qt.Key.Key_Down)  == "down"
        assert self.fn(Qt.Key.Key_Left)  == "left"
        assert self.fn(Qt.Key.Key_Right) == "right"

    def test_alphanumeric_lowercase(self):
        assert self.fn(ord("A")) == "a"
        assert self.fn(ord("Z")) == "z"
        assert self.fn(ord("0")) == "0"
        assert self.fn(ord("9")) == "9"

    def test_unknown_key_returns_none(self):
        assert self.fn(9999) is None


# ── ortak fixture ─────────────────────────────────────────────────────────────

@pytest.fixture
def dashboard(qapp, mock_settings):
    from ui.dashboard import DashboardWindow
    w = DashboardWindow(mock_settings, icon_idle=_make_icon())
    yield w
    w.close()


# ──────────────────────────────────────────────────────────────────────────────

class TestDashboardLog:
    def test_append_log_adds_entry(self, dashboard):
        dashboard.append_log_entry("...", "APP","test mesajı")
        assert "test mesajı" in dashboard.log_box.toPlainText()

    def test_append_log_adds_timestamp(self, dashboard):
        dashboard.append_log_entry("...", "APP","zaman damgası testi")
        content = dashboard.log_box.toPlainText()
        assert "[" in content and "]" in content

    def test_append_log_100_line_limit(self, dashboard):
        for i in range(150):
            dashboard.append_log_entry("...", "APP",f"satır {i}")
        assert dashboard.log_box.document().blockCount() <= 101

    def test_append_multiple_logs(self, dashboard):
        dashboard.append_log_entry("...", "APP","birinci")
        dashboard.append_log_entry("...", "APP","ikinci")
        content = dashboard.log_box.toPlainText()
        assert "birinci" in content
        assert "ikinci" in content

    def test_log_colors_update_after_theme_change(self, dashboard):
        from ui.theme import theme_manager, DARK_PALETTE
        ALT_PALETTE = {**DARK_PALETTE, "CLR_OK": "#aabbcc"}
        theme_manager.palette = DARK_PALETTE
        dashboard._update_log_stylesheet()
        dashboard.append_log_entry("OK", "APP", "mesaj")
        # Alternatif palete geç, log yeniden render edilmeli
        theme_manager.palette = ALT_PALETTE
        dashboard._update_log_stylesheet()
        log_html = dashboard.log_box.toHtml()
        assert ALT_PALETTE["CLR_OK"] in log_html
        assert DARK_PALETTE["CLR_OK"] not in log_html

    def test_log_entries_survive_theme_change(self, dashboard):
        dashboard.append_log_entry("OK", "APP", "kayıt sonrası mesaj")
        dashboard._update_log_stylesheet()
        assert "kayıt sonrası mesaj" in dashboard.log_box.toPlainText()

    def test_log_entries_list_capped_at_100(self, dashboard):
        for i in range(150):
            dashboard.append_log_entry("...", "APP", f"satır {i}")
        assert len(dashboard._log_entries) <= 100


class TestDashboardStatus:
    def test_set_status_text(self, dashboard):
        from core.settings import STATE_LISTENING
        from core.i18n import t
        dashboard.set_status(STATE_LISTENING)
        assert t(STATE_LISTENING) in dashboard.status_label.text()

    def test_set_status_color(self, dashboard):
        from ui.theme import theme_manager
        dashboard.set_status("Hata", "ERR")
        assert theme_manager.palette["CLR_TEXT_STATUS"] in dashboard.status_label.text()

    def test_default_status_is_waiting(self, dashboard):
        from core.settings import STATE_READY
        from core.i18n import t
        assert t(STATE_READY) in dashboard.status_label.text()


class TestDashboardLevel:
    def test_update_level_zero(self, dashboard):
        dashboard.update_level(0.0)
        assert dashboard.level_bar.value() == 0

    def test_update_level_full(self, dashboard):
        from core.settings import STATE_LISTENING
        dashboard.set_status(STATE_LISTENING)
        dashboard.update_level(1.0)
        assert dashboard.level_bar.value() == 100

    def test_update_level_green_range(self, dashboard):
        from ui.theme import theme_manager
        from core.settings import STATE_LISTENING
        dashboard.set_status(STATE_LISTENING)
        dashboard.update_level(0.3)
        assert theme_manager.palette["CLR_OK"] in dashboard.level_bar.styleSheet()

    def test_update_level_yellow_range(self, dashboard):
        from ui.theme import theme_manager
        from core.settings import STATE_LISTENING
        dashboard.set_status(STATE_LISTENING)
        dashboard.update_level(0.7)
        assert theme_manager.palette["CLR_WARN"] in dashboard.level_bar.styleSheet()

    def test_update_level_red_range(self, dashboard):
        from ui.theme import theme_manager
        from core.settings import STATE_LISTENING
        dashboard.set_status(STATE_LISTENING)
        dashboard.update_level(0.95)
        assert theme_manager.palette["CLR_ERR"] in dashboard.level_bar.styleSheet()

    def test_update_level_clamped(self, dashboard):
        from core.settings import STATE_LISTENING
        dashboard.set_status(STATE_LISTENING)
        dashboard.update_level(1.5)
        assert dashboard.level_bar.value() == 100


class TestPopulateDevices:
    def test_populate_fills_combo(self, dashboard):
        dashboard.populate_devices([("Mikrofon A", 0, False), ("★ Mikrofon B", 2, True)])
        assert dashboard.mic_combo.count() == 2

    def test_populate_stores_device_index(self, dashboard):
        dashboard.populate_devices([("★ Mikrofon A", 3, True)])
        assert dashboard.mic_combo.itemData(0) == 3

    def test_populate_selects_default(self, dashboard):
        dashboard.settings.set("mic_index", None)
        dashboard.populate_devices([("Mikrofon A", 0, False), ("★ Mikrofon B", 2, True)])
        assert dashboard.mic_combo.currentData() == 2

    def test_populate_empty_list_clears_combo(self, dashboard):
        dashboard.populate_devices([("Eski", 0, False)])
        dashboard.populate_devices([])
        assert dashboard.mic_combo.count() == 0

    def test_populate_clears_previous_items(self, dashboard):
        dashboard.populate_devices([("Eski", 0, False)])
        dashboard.populate_devices([("Yeni A", 1, True), ("Yeni B", 2, False)])
        assert dashboard.mic_combo.count() == 2
        assert dashboard.mic_combo.itemText(0) == "Yeni A"

    def test_refresh_button_emits_signal(self, dashboard):
        received = []
        dashboard.refresh_devices_requested.connect(lambda: received.append(1))
        dashboard._populate_devices()
        assert len(received) == 1

    def test_populate_emits_device_changed_for_selected(self, dashboard):
        """Combo dolduğunda seçili cihaz device_changed ile iletilmeli."""
        changed = []
        dashboard.device_changed.connect(changed.append)
        dashboard.populate_devices([("★ Mikrofon", 42, True)])
        assert changed == [42]

    def test_populate_no_items_does_not_emit_device_changed(self, dashboard):
        """Boş liste gelince device_changed çıkmamalı."""
        changed = []
        dashboard.device_changed.connect(changed.append)
        dashboard.populate_devices([])
        assert changed == []


class TestTrayApp:
    def test_tray_app_creates_dashboard(self, qapp, mock_settings):
        from ui.tray_app import TrayApp
        tray = TrayApp(mock_settings)
        assert tray.dashboard is not None
        tray.tray.hide()
        tray.dashboard.close()

    def test_set_recording_true(self, qapp, mock_settings):
        from ui.tray_app import TrayApp
        tray = TrayApp(mock_settings)
        tray.set_recording(True)
        from core.settings import STATE_LISTENING
        from core.i18n import t
        assert t(STATE_LISTENING) in tray.dashboard.status_label.text()
        tray.tray.hide()
        tray.dashboard.close()

    def test_set_recording_false(self, qapp, mock_settings):
        from ui.tray_app import TrayApp
        tray = TrayApp(mock_settings)
        tray.set_recording(False)
        from core.settings import STATE_READY
        from core.i18n import t
        assert t(STATE_READY) in tray.dashboard.status_label.text()
        tray.tray.hide()
        tray.dashboard.close()

    def test_on_tray_activated(self, qapp, mock_settings):
        from ui.tray_app import TrayApp
        from PySide6.QtWidgets import QSystemTrayIcon
        tray = TrayApp(mock_settings)
        with patch.object(tray, "_show_dashboard") as mock_show:
            tray._on_tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
            mock_show.assert_called_once()
            tray._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
            mock_show.assert_called_once()  # Sadece çift tıklamada tetiklenmeli
        tray.tray.hide()
        tray.dashboard.close()

    def test_show_dashboard(self, qapp, mock_settings):
        from ui.tray_app import TrayApp
        tray = TrayApp(mock_settings)
        tray._show_dashboard()
        assert tray.dashboard.isVisible()
        tray.tray.hide()
        tray.dashboard.close()

    def test_on_hotkey_pressed(self, qapp, mock_settings):
        from ui.tray_app import TrayApp
        tray = TrayApp(mock_settings)
        tray.audio_worker = MagicMock()
        tray.on_hotkey_pressed()
        tray.audio_worker.start_recording.assert_called_once()
        tray.tray.hide()
        tray.dashboard.close()

    def test_on_hotkey_pressed_model_not_ready_blocks_recording(self, qapp, mock_settings):
        """Model hazır değilse kayıt başlamamalı."""
        from ui.tray_app import TrayApp
        tray = TrayApp(mock_settings)
        tray.audio_worker = MagicMock()
        tray.transcription_worker = MagicMock()
        tray.transcription_worker.is_ready = False
        tray.on_hotkey_pressed()
        tray.audio_worker.start_recording.assert_not_called()
        tray.tray.hide()
        tray.dashboard.close()

    def test_on_hotkey_pressed_model_not_ready_shows_osd_error(self, qapp, mock_settings):
        """Model hazır değilse OSD hata durumuna geçmeli."""
        from ui.tray_app import TrayApp
        tray = TrayApp(mock_settings)
        tray.transcription_worker = MagicMock()
        tray.transcription_worker.is_ready = False
        tray.osd = MagicMock()
        tray.on_hotkey_pressed()
        tray.osd.setStateError.assert_called_once_with("status.no_model")
        tray.tray.hide()
        tray.dashboard.close()

    def test_on_hotkey_pressed_model_not_ready_does_not_set_recording_state(self, qapp, mock_settings):
        """Model hazır değilse dashboard 'Dinliyor' göstermemeli."""
        from ui.tray_app import TrayApp
        tray = TrayApp(mock_settings)
        tray.transcription_worker = MagicMock()
        tray.transcription_worker.is_ready = False
        tray.on_hotkey_pressed()
        from core.settings import STATE_LISTENING
        assert STATE_LISTENING not in tray.dashboard.status_label.text()
        tray.tray.hide()
        tray.dashboard.close()

    def test_on_hotkey_released(self, qapp, mock_settings):
        from ui.tray_app import TrayApp
        tray = TrayApp(mock_settings)
        tray.audio_worker = MagicMock()
        tray.on_hotkey_released()
        tray.audio_worker.stop_recording.assert_called_once()
        tray.tray.hide()
        tray.dashboard.close()



class TestDashboardKeyPress:
    def test_escape_hides_window(self, dashboard):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        dashboard.show()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        dashboard.keyPressEvent(event)
        assert not dashboard.isVisible()

    def test_other_key_does_not_hide(self, dashboard):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        dashboard.show()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        dashboard.keyPressEvent(event)
        assert dashboard.isVisible()


class TestDashboardLoadingIndicator:
    def test_set_loading_indicator_true_shows_spinner(self, dashboard):
        dashboard.set_loading_indicator(True)
        assert dashboard.level_bar.maximum() == 0  # Sonsuz (Indeterminate) mod

    def test_set_loading_indicator_false_hides_spinner(self, dashboard):
        dashboard.set_loading_indicator(True)
        dashboard.set_loading_indicator(False)
        assert dashboard.level_bar.maximum() == 100 # Normal mod



class TestDashboardExtras:
    def test_apply_dark_mode_exception(self, qapp, mock_settings):
        from ui.dashboard import DashboardWindow
        with patch("ui.dashboard.apply_dark_mode_to_window", side_effect=Exception("No DWM")):
            w = DashboardWindow(mock_settings, icon_idle=_make_icon())
            assert w is not None

    def test_on_audio_inputs_changed(self, dashboard):
        with patch.object(dashboard, "_populate_devices") as mock_pop:
            dashboard._on_audio_inputs_changed()
            mock_pop.assert_called_once()

    def test_populate_devices_early_return(self, dashboard):
        items = [("A", 1, True)]
        dashboard.populate_devices(items)
        with patch.object(dashboard.mic_combo, "blockSignals") as mock_block:
            dashboard.populate_devices(items)
            mock_block.assert_not_called() 

    def test_public_methods(self, dashboard):
        assert dashboard.selected_device_index() is None
        dashboard.show_help()
        assert dashboard._help_window.isVisible()
        received_hotkeys = []
        dashboard.hotkey_changed.connect(received_hotkeys.append)
        dashboard._on_hotkey_from_dialog("F12")
        assert len(received_hotkeys) == 1
        assert received_hotkeys[0] == "F12"