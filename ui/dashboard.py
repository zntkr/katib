import os
import html

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QTextBrowser, QPushButton,
    QSizePolicy, QProgressBar,
)
from PySide6.QtCore import Qt, QDateTime, Signal, QTimer, QSize
from PySide6.QtGui import (
    QIcon, QFont, QColor,
    QPainter, QPaintEvent, QShowEvent, QKeyEvent
)

from core.settings import APP_NAME, STATE_READY
from core.i18n import t
from ui.theme import theme_manager, G_1, G_4, FONT_SIZE_SM, FONT_SIZE_LG, PANEL_WIDTH, COMBO_HEIGHT, LOG_BOX_HEIGHT

_LEVEL_PALETTE_KEY: dict[str, str] = {
    "OK":   "CLR_OK",
    "ERR":  "CLR_ERR",
    "WARN": "CLR_WARN",
    "WRN":  "CLR_WARN",
    "IDLE": "CLR_WARN",  # model loading (orange)
    "...":  "CLR_INFO",
    "INFO": "CLR_INFO",
    "↓":    "CLR_INFO",
}
from ui.utils_win import apply_dark_mode_to_window

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.help_window import HelpWindow
    from ui.settings_dialog import SettingsDialog

from ui.icons import ICN_COPY, ICN_TERMINAL, ICN_SETTINGS, ICN_DOT
from ui.components import NoScrollComboBox, DynamicIconButton

class DashboardWindow(QWidget):
    device_changed            = Signal(int)
    hotkey_changed            = Signal(str)
    hotkey_capture_mode       = Signal(bool)  # True=capture started, False=finished
    model_dir_changed         = Signal(str)
    model_reload_requested    = Signal()
    refresh_devices_requested = Signal()
    download_model_requested  = Signal(str, str)
    language_change_requested = Signal(str)
    theme_changed             = Signal(str)

    def __init__(self, settings, icon_idle: QIcon, parent: QWidget | None = None):
        flags = (
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        super().__init__(parent, flags)
        self.setObjectName("DashboardWindow")
        self.settings = settings
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon_idle)

        # ── White Flash Prevention ────────────────────────────────────────
        # WA_TranslucentBackground: DWM initialises the buffer as transparent
        # instead of white; Qt paints the dark background on the first paint —
        # the user never sees a white flash.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # ─────────────────────────────────────────────────────────────────

        # ── Windows DWM Dark Mode ──────────────────────────────────────────
        try:
            apply_dark_mode_to_window(int(self.winId()))
        except Exception:
            pass
        # ───────────────────────────────────────────────────────────────────

        self._last_devices = None
        self._last_transcript: str | None = None

        self._build_ui()

        # Listen for OS hardware events (deferred to avoid blocking __init__).
        QTimer.singleShot(100, self._init_media_devices)

    def _init_media_devices(self):
        from PySide6.QtMultimedia import QMediaDevices
        self._media_devices = QMediaDevices(self)
        self._media_devices.audioInputsChanged.connect(self._on_audio_inputs_changed)
        
        # Debounce: hardware events (plug/unplug) can fire dozens of times per second.
        self._device_refresh_timer = QTimer(self)
        self._device_refresh_timer.setSingleShot(True)
        self._device_refresh_timer.setInterval(500)  # wait 500 ms for the signal storm to settle
        self._device_refresh_timer.timeout.connect(self._do_audio_inputs_changed)

    def _on_audio_inputs_changed(self) -> None:
        # In test environments this method may be called before the timer is initialised.
        if hasattr(self, "_device_refresh_timer"):
            self._device_refresh_timer.start()  # restart the timer on every new signal
        else:
            self._do_audio_inputs_changed()

    def _do_audio_inputs_changed(self) -> None:
        self.append_log_entry("...", "MIC", "", "dashboard.device_refreshed")
        self._populate_devices()

    # ------------------------------------------------------------------ build
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(G_1, G_1, G_1, G_1)
        root.setSpacing(G_1)
        
        p = theme_manager.palette
        
        # ── LOG AREA (Top Layer) ──────────────────────────────────────
        self.log_widget = QWidget()
        self.log_widget.setObjectName("log_widget")
        log_layout = QVBoxLayout(self.log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(G_1)
        
        self.log_box = QTextBrowser()
        self.log_box.setObjectName("log_box")
        self.log_box.setOpenExternalLinks(False)
        self.log_box.setFont(QFont("Consolas", FONT_SIZE_SM))
        self.log_box.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.log_box.setFixedHeight(LOG_BOX_HEIGHT)
        self.log_box.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.log_box.document().setMaximumBlockCount(100)
        self._log_entries: list[tuple[str, str, str, str, str]] = []
        log_layout.addWidget(self.log_box)

        root.addWidget(self.log_widget)
        self.log_widget.hide()

        # ── STATUS & LEVEL ROW (Middle Layer) ─────────────────────────
        status_row = QHBoxLayout()
        status_row.setSpacing(G_1)
        status_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        badge_layout = QHBoxLayout()
        badge_layout.setSpacing(4)
        
        self.status_icon_label = QLabel()
        self.status_icon_label.setFixedSize(14, 14)
        self.status_icon_label.mousePressEvent = self._on_status_label_click
        badge_layout.addWidget(self.status_icon_label)

        self.status_label = QLabel("")
        self.status_label.setFixedHeight(G_4)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._status_cache: tuple[str, str] = (STATE_READY, "OK")
        self._status_clickable = False
        self.status_label.mousePressEvent = self._on_status_label_click
        badge_layout.addWidget(self.status_label)
        
        status_row.addLayout(badge_layout)
        
        self.level_bar = QProgressBar()
        self.level_bar.setObjectName("level_bar")
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedHeight(8)
        self.level_bar.setMinimumWidth(48)
        self.level_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        status_row.addWidget(self.level_bar)
        
        self.btn_copy_transcript = DynamicIconButton(ICN_COPY, p["CLR_OK"], "")
        self.btn_copy_transcript.setObjectName("btn_copy_transcript")
        self.btn_copy_transcript.setFixedSize(G_4, G_4)
        self.btn_copy_transcript.setToolTip(t("dashboard.copy_tooltip"))
        self.btn_copy_transcript.setEnabled(False)
        self.btn_copy_transcript.clicked.connect(self._copy_last_transcript)
        status_row.addWidget(self.btn_copy_transcript)

        self.btn_toggle_log = DynamicIconButton(ICN_TERMINAL, p["CLR_YELLOW"], "\uE756", idle_color=p["CLR_FG3"])
        self.btn_toggle_log.setObjectName("btn_toggle_log")
        self.btn_toggle_log.setFixedSize(G_4, G_4)
        self.btn_toggle_log.setToolTip(t("dashboard.console_tooltip"))
        self.btn_toggle_log.clicked.connect(self._toggle_logs)
        status_row.addWidget(self.btn_toggle_log)
        
        root.addLayout(status_row)

        # ── COMPACT HUD (Bottom Layer) ────────────────────────────────
        mic_row = QHBoxLayout()
        mic_row.setSpacing(G_1)
        
        self.mic_combo = NoScrollComboBox()
        self.mic_combo.currentIndexChanged.connect(self._on_device_changed)
        mic_row.addWidget(self.mic_combo)
        
        self.btn_settings = DynamicIconButton(ICN_SETTINGS, p["CLR_YELLOW"], "\uE713", idle_color=p["CLR_FG3"])
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.setFixedSize(G_4, G_4)
        self.btn_settings.setToolTip(t("dashboard.settings_tooltip"))
        self.btn_settings.clicked.connect(self._open_settings_dialog)
        mic_row.addWidget(self.btn_settings)
        
        root.addLayout(mic_row)

        self._help_window: 'HelpWindow | None' = None
        self._settings_dialog: 'SettingsDialog | None' = None

        self.setFixedWidth(PANEL_WIDTH)
        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())

        # Apply styles after the full UI (including the status bar) is built.
        self._update_log_stylesheet()

    def _toggle_logs(self) -> None:
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)

        old_bottom = self.y() + self.height()

        if self.log_widget.isVisible():
            self.log_widget.hide()
        else:
            self.log_widget.show()

        self._update_log_btn_style()

        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())

        # Keep the bottom edge fixed — the window grows/shrinks upward without repositioning.
        self.move(self.x(), old_bottom - self.height())

    def _update_log_btn_style(self) -> None:
        is_active = self.log_widget.isVisible()
        self.btn_toggle_log.setProperty("isActive", is_active)
        self.btn_toggle_log.set_active(is_active)
        self.btn_toggle_log.style().unpolish(self.btn_toggle_log)
        self.btn_toggle_log.style().polish(self.btn_toggle_log)

    # ---------------------------------------------------------------- helpers
    def _copy_last_transcript(self) -> None:
        if self._last_transcript:
            QApplication.clipboard().setText(self._last_transcript)
            self.btn_copy_transcript.setToolTip(t("dashboard.copied_tooltip"))
            QTimer.singleShot(1500, lambda: self.btn_copy_transcript.setToolTip(t("dashboard.copy_tooltip")))

    def set_last_transcript(self, text: str) -> None:
        self._last_transcript = text
        self.btn_copy_transcript.setEnabled(True)

    def _populate_devices(self) -> None:
        self.refresh_devices_requested.emit()

    def populate_devices(self, items: list[tuple[str, int, bool]]) -> None:
        """Populates the combo box from the list provided by AudioWorker's devices_ready signal."""
        if getattr(self, "_last_devices", None) == items:
            return
        self._last_devices = items
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        saved_device  = self.settings.get("device_index")
        saved_device_name = self.settings.get("device_name")
        preferred_idx = -1
        default_idx   = -1
        for i, (label, index, is_default) in enumerate(items):
            # Strip hidden newline characters that appear in some Windows driver names.
            label = label.replace("\r", "").replace("\n", " ").strip()
            
            self.mic_combo.addItem(label, userData=index)
            clean_label = label.replace(" (Default)", "")
            if saved_device_name:
                if clean_label == saved_device_name:
                    preferred_idx = i
            elif index == saved_device:
                preferred_idx = i
            if is_default:
                default_idx = i
        select_idx = preferred_idx if preferred_idx != -1 else default_idx
        if select_idx == -1 and items:
            select_idx = 0
        if select_idx != -1:
            self.mic_combo.setCurrentIndex(select_idx)
        if not items:
            self.append_log_entry("WRN", "MIC", "", "dashboard.no_mic_found")
            self.mic_combo.setPlaceholderText(t("dashboard.no_mic_found"))
            self.mic_combo.setCurrentIndex(-1)
            self.mic_combo.setEnabled(False)
        else:
            self.mic_combo.setPlaceholderText("")
            self.mic_combo.setEnabled(True)
        self.mic_combo.blockSignals(False)
        # setCurrentIndex did not emit a signal because signals were blocked; notify the worker manually.
        if select_idx != -1:
            device_data = self.mic_combo.itemData(select_idx)
            if device_data is not None:
                reason = "Saved Preference" if preferred_idx != -1 else "System Default"
                clean_name = self.mic_combo.itemText(select_idx).replace(" (Default)", "")
                self.append_log_entry("...", "MIC", f"Auto-selected: {clean_name} ({reason})")
                
                # Do NOT write settings here — only save when the user changes the device via _on_device_changed.
                # self.settings.set("device_name", clean_name)
                # self.settings.set("device_index", device_data)
                self.device_changed.emit(device_data)

    def _position_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        geo = self.frameGeometry()
        
        x = screen.x() + screen.width() - geo.width()
        y = screen.y() + screen.height() - geo.height()
        
        from ui.utils_win import get_dwm_visual_bounds
        bounds = get_dwm_visual_bounds(int(self.winId()))
        if bounds:
            dpr = QApplication.primaryScreen().devicePixelRatio()
            _, _, d_right, d_bottom = bounds
            offset_right = int(d_right / dpr) - geo.x()
            offset_bottom = int(d_bottom / dpr) - geo.y()
            x = screen.x() + screen.width() - offset_right
            y = screen.y() + screen.height() - offset_bottom

        self.move(x, y)

    def showEvent(self, event: QShowEvent) -> None:
        self.setWindowOpacity(0.0)
        self.adjustSize()
        super().showEvent(event)
        
        def _finalize_position():
            self._position_bottom_right()
            self.setWindowOpacity(1.0)
            
        # Position asynchronously so the Windows frame is already attached.
        QTimer.singleShot(15, _finalize_position)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Fills layout gaps with the background colour — WA_TranslucentBackground
        prevents QSS from reaching those areas."""
        from ui.theme import theme_manager
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme_manager.palette["CLR_BG"]))
        painter.end()
        super().paintEvent(event)

    def _on_device_changed(self, combo_idx: int):
        device_idx = self.mic_combo.itemData(combo_idx)
        if device_idx is not None:
            raw_text = self.mic_combo.itemText(combo_idx)
            clean_name = raw_text.replace(" (Default)", "")

            if " (Default)" in raw_text:
                self.settings.set("device_index", -1)
                self.settings.set("device_name", "")
                self.append_log_entry("...", "MIC", "Switched to dynamic default tracking.")
            else:
                self.settings.set("device_index", device_idx)
                self.settings.set("device_name", clean_name)
                self.append_log_entry("...", "MIC", f"Microphone locked: {clean_name}")
                
            self.device_changed.emit(device_idx)

# ----------------------------------------------------------------- public
    def set_loading_indicator(self, visible: bool):
        if visible:
            self.level_bar.setRange(0, 0)  # indeterminate (infinite) loading mode
            p = theme_manager.palette
            self.level_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {p['CLR_YELLOW']}; border-radius: 2px; }}")
            self._last_level_color = p["CLR_YELLOW"]
        else:
            self.level_bar.setRange(0, 100)  # return to normal mode
            self.level_bar.setValue(0)
            self.update_level(0.0)

    def _make_log_html_line(self, level: str, component: str, message: str, ts: str) -> str:
        _DISPLAY: dict[str, str] = {"...": "INFO"}
        lv = _DISPLAY.get(level.strip(), level.strip())[:4].ljust(4).replace(" ", "&nbsp;")
        cp = component.strip()[:3].ljust(3).replace(" ", "&nbsp;")
        safe_msg = html.escape(message)
        p = theme_manager.palette
        palette_key = _LEVEL_PALETTE_KEY.get(level.strip())
        lvl_color = p.get(palette_key, p["CLR_TEXT"]) if palette_key else p["CLR_TEXT"]
        c_ts  = p["CLR_TEXT_FAINT"]
        c_cp  = p["CLR_TEXT_MUTED"]
        c_msg = p["CLR_TEXT_CONTENT"]
        return (
            f"<span style='color:{c_ts}'>[{ts}]</span>&nbsp;&nbsp;"
            f"<span style='color:{lvl_color};font-weight:bold'>{lv}</span>&nbsp;&nbsp;"
            f"<span style='color:{c_cp}'>{cp}</span>&nbsp;&nbsp;"
            f"<span style='color:{c_msg}'>{safe_msg}</span>"
        )

    def _update_log_stylesheet(self, *_args):
        self.log_box.document().clear()
        for level, component, message, i18n_key, ts in self._log_entries:
            display = t(i18n_key) if i18n_key else message
            self.log_box.append(self._make_log_html_line(level, component, display, ts))
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())
        self.set_status(*self._status_cache)

    def append_log_entry(self, level: str, component: str, message: str, i18n_key: str = "") -> None:
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self._log_entries.append((level, component, message, i18n_key, ts))
        if len(self._log_entries) > 100:
            self._log_entries = self._log_entries[-100:]
        display = t(i18n_key) if i18n_key else message
        self.log_box.append(self._make_log_html_line(level, component, display, ts))
        scrollbar = self.log_box.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_level(self, value: float):
        if self.level_bar.maximum() == 0:
            return  # ignore microphone signals while the bar is in loading mode

        from core.settings import STATE_LISTENING
        if value > 0.0 and self._status_cache[0] != STATE_LISTENING:
            return  # ignore delayed signals that arrive after recording has stopped

        pct = max(0, min(100, int(value * 100)))
        self.level_bar.setValue(pct)
        p = theme_manager.palette
        if pct < 25:
            color = p["CLR_INFO"]
        elif pct < 50:
            color = p["CLR_OK"]
        elif pct < 75:
            color = p["CLR_WARN"]
        else:
            color = p["CLR_ERR"]
        # The global stylesheet cannot dynamically colour ::chunk by a property value,
        # so we use a small inline override instead.
        if getattr(self, '_last_level_color', None) != color:
            self._last_level_color = color
            self.level_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {color}; border-radius: 2px; }}"
            )

    def set_status(self, text: str, level: str = "OK"):
        self._status_cache = (text, level)
        text = t(text)
        text = text[:1].upper() + text[1:]
        p = theme_manager.palette

        # The icon (LED) takes the status colour; the text always stays muted.
        icon_color = p.get(_LEVEL_PALETTE_KEY.get(level, "CLR_IDLE"), p["CLR_TEXT_MUTED"])
        text_color = p["CLR_TEXT_STATUS"]
        
        from ui.utils import colorize_svg_icon
            
        icon_pixmap = colorize_svg_icon(ICN_DOT, icon_color).pixmap(14, 14)
        self.status_icon_label.setPixmap(icon_pixmap)

        safe_text = html.escape(text)
        self.status_label.setText(f"<span style='color: {text_color};'>{safe_text}</span>")
        self.status_label.setStyleSheet("font-weight: bold;")

    def _on_status_label_click(self, _event) -> None:
        if self._status_clickable:
            self._open_settings_dialog()
            if self._settings_dialog:
                self._settings_dialog.focus_model()

    def show_model_missing_guidance(self) -> None:
        self.append_log_entry("INFO", "STT", "", "dashboard.model_missing_guidance")
        if not self.log_widget.isVisible():
            self._toggle_logs()
        self._status_clickable = True
        self.status_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
        def _auto_open():
            self._open_settings_dialog()
            if self._settings_dialog:
                self._settings_dialog.focus_model()
        QTimer.singleShot(50, _auto_open)

    def clear_model_missing_guidance(self) -> None:
        self._status_clickable = False
        self.status_label.unsetCursor()
        self.status_icon_label.unsetCursor()

    def closeEvent(self, event) -> None:
        """Stops active QTimers on teardown to prevent memory leaks."""
        for timer in self.findChildren(QTimer):
            if timer.isActive():
                timer.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def selected_device_index(self) -> int | None:
        return self.mic_combo.currentData()

    def set_download_state(self, active: bool) -> None:
        self.set_loading_indicator(active)
        if self._settings_dialog is not None:
            self._settings_dialog.set_download_state(active)

    def on_download_complete(self, model_dir: str) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.on_download_complete(model_dir)
        self.model_dir_changed.emit(model_dir)

    def show_help(self):
        from ui.help_window import HelpWindow
        if self._help_window is None:
            self._help_window = HelpWindow(settings=self.settings)
        self._help_window.show()
        self._help_window.raise_()
        self._help_window.activateWindow()
        QTimer.singleShot(10, self._position_help_beside_dashboard)

    def _position_help_beside_dashboard(self) -> None:
        if self._help_window is None:
            return
        screen = QApplication.primaryScreen().availableGeometry()
        dash_geo = self.frameGeometry()
        help_geo = self._help_window.frameGeometry()

        x = dash_geo.x() - help_geo.width() - 5
        y = screen.y() + screen.height() - help_geo.height()

        from ui.utils_win import get_dwm_visual_bounds
        bounds = get_dwm_visual_bounds(int(self._help_window.winId()))
        if bounds:
            dpr = QApplication.primaryScreen().devicePixelRatio()
            _, _, _, d_bottom = bounds
            offset_bottom = int(d_bottom / dpr) - self._help_window.y()
            y = screen.y() + screen.height() - offset_bottom

        if x < screen.left():
            x = dash_geo.right() + 5

        self._help_window.move(x, y)

    def _open_settings_dialog(self) -> None:
        from ui.settings_dialog import SettingsDialog
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.close()
            return

        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(settings=self.settings, parent=self)
            self._settings_dialog.hotkey_changed.connect(self._on_hotkey_from_dialog)
            self._settings_dialog.capture_mode_changed.connect(self.hotkey_capture_mode)
            self._settings_dialog.model_dir_changed.connect(self.model_dir_changed)
            self._settings_dialog.model_reload_requested.connect(self.model_reload_requested)
            self._settings_dialog.download_model_requested.connect(self.download_model_requested)
            self._settings_dialog.log_entry.connect(self.append_log_entry)
            self._settings_dialog.finished.connect(self._update_settings_btn_style)
            self._settings_dialog.language_change_requested.connect(self.language_change_requested)
            self._settings_dialog.theme_changed.connect(self.theme_changed)

        # Sidecar alignment — same formula as _position_bottom_right:
        # availableGeometry + DWM visual bounds for bottom-edge alignment.
        self._settings_dialog.setWindowOpacity(0.0)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()
        self._update_settings_btn_style()
        QTimer.singleShot(10, self._position_settings_beside_dashboard)

    def refresh_theme(self) -> None:
        from ui.theme import theme_manager
        p = theme_manager.palette
        self.btn_copy_transcript.recolor(p["CLR_OK"])
        self.btn_toggle_log.recolor(p["CLR_YELLOW"], idle_color=p["CLR_FG3"])
        self.btn_settings.recolor(p["CLR_YELLOW"], idle_color=p["CLR_FG3"])
        self._update_log_stylesheet()

    def _refresh_language_tooltips(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.btn_copy_transcript.setToolTip(t("dashboard.copy_tooltip"))
        self.btn_toggle_log.setToolTip(t("dashboard.console_tooltip"))
        self.btn_settings.setToolTip(t("dashboard.settings_tooltip"))
        self.set_status(*self._status_cache)
        self._update_log_stylesheet()

    def _update_settings_btn_style(self, *_) -> None:
        is_active = self._settings_dialog is not None and self._settings_dialog.isVisible()
        self.btn_settings.setProperty("isActive", is_active)
        self.btn_settings.set_active(is_active)
        self.btn_settings.style().unpolish(self.btn_settings)
        self.btn_settings.style().polish(self.btn_settings)

    def _position_settings_beside_dashboard(self) -> None:
        if self._settings_dialog is None:
            return
        screen = QApplication.primaryScreen().availableGeometry()
        dash_geo = self.frameGeometry()
        sett_geo = self._settings_dialog.frameGeometry()

        x = dash_geo.x() - sett_geo.width() - 5
        y = screen.y() + screen.height() - sett_geo.height()

        from ui.utils_win import get_dwm_visual_bounds
        bounds = get_dwm_visual_bounds(int(self._settings_dialog.winId()))
        if bounds:
            dpr = QApplication.primaryScreen().devicePixelRatio()
            _, _, _, d_bottom = bounds
            offset_bottom = int(d_bottom / dpr) - self._settings_dialog.y()
            y = screen.y() + screen.height() - offset_bottom

        if x < screen.left():
            x = dash_geo.right() + 5

        self._settings_dialog.move(x, y)
        self._settings_dialog.setWindowOpacity(1.0)

    def _on_hotkey_from_dialog(self, key: str) -> None:
        self.hotkey_changed.emit(key)