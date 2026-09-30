from typing import TYPE_CHECKING
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QPushButton, QVBoxLayout
from PySide6.QtCore import QObject, Slot, QTimer

from core.settings import APP_NAME, MSG_MIC_UNAVAILABLE, MSG_MODEL_NOT_FOUND, STATE_LISTENING, STATE_READY, STATE_LOADING
from core.i18n import t
from PySide6.QtGui import QIcon
from ui.utils import colorize_svg_icon
from ui.theme import theme_manager
from ui.icons import ICN_MIC
from ui.dashboard import DashboardWindow

if TYPE_CHECKING:
    from workers.audio_worker import AudioWorker
    from ui.osd import MinimalOSD
    from workers.transcription_worker import TranscriptionWorker

class TrayApp(QObject):
    """
    Does not inherit from QApplication.
    Instantiated AFTER QApplication is created in main.py.
    """

    def __init__(self, settings, model_provider, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings
        self.model_provider = model_provider

        self.audio_worker: 'AudioWorker | None' = None
        self.transcription_worker: 'TranscriptionWorker | None' = None
        self.osd: 'MinimalOSD | None' = None
        self._mic_unavailable: bool = False

        p = theme_manager.palette
        self._icon_idle = colorize_svg_icon(ICN_MIC, p["CLR_TEXT_MUTED"], size=64)
        self._icon_rec  = colorize_svg_icon(ICN_MIC, p["CLR_ERR"], size=64)

        self.dashboard = DashboardWindow(settings=self.settings, model_provider=self.model_provider, icon_idle=self._icon_idle)

        # The tray icon object always exists so icon/tooltip updates never need a
        # guard; it is only shown once the OS actually provides a system tray.
        self._build_tray()
        self._no_tray_quit_btn: QPushButton | None = None
        self._tray_retry_count = 0
        self._tray_retry_timer = QTimer(self)
        self._tray_retry_timer.setInterval(self.TRAY_RETRY_INTERVAL_MS)
        self._tray_retry_timer.timeout.connect(self._retry_tray)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            # e.g. autostart at login before Explorer has created the taskbar
            self._build_no_tray_quit_button()
            self._tray_retry_timer.start()

    _RTL_LANGS = {"ar", "fa", "ur"}
    TRAY_RETRY_INTERVAL_MS = 5000
    TRAY_RETRY_LIMIT       = 60  # give up after 5 minutes

    # ------------------------------------------------------------------ tray
    @Slot(str)
    def apply_language(self, lang_code: str) -> None:
        from PySide6.QtCore import Qt
        from core.i18n import set_language
        set_language(lang_code)
        direction = Qt.LayoutDirection.RightToLeft if lang_code in self._RTL_LANGS else Qt.LayoutDirection.LeftToRight
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setLayoutDirection(direction)
        self.tray.hide()
        self.tray.deleteLater()
        self._build_tray()
        self.dashboard._refresh_language_tooltips()
        if self.osd:
            self.osd.refresh_language()
        QTimer.singleShot(0, self._reopen_settings_after_language_change)

    def _reopen_settings_after_language_change(self) -> None:
        dlg = self.dashboard._settings_dialog
        was_visible = dlg is not None and dlg.isVisible()
        if dlg is not None:
            dlg.close()
            self.dashboard._settings_dialog = None
        if was_visible:
            self.dashboard._open_settings_dialog()

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self._icon_idle)
        self.tray.setToolTip(f"{APP_NAME} — {t(STATE_READY)}")

        menu = QMenu()
        act_panel = menu.addAction(t("tray.menu.dashboard"))
        act_settings = menu.addAction(t("tray.menu.settings"))
        act_help  = menu.addAction(t("tray.menu.user_guide"))
        menu.addSeparator()
        act_quit  = menu.addAction(t("tray.menu.quit"))

        act_panel.triggered.connect(self._show_dashboard)
        act_settings.triggered.connect(self.dashboard._open_settings_dialog)
        act_help.triggered.connect(self.dashboard.show_help)
        app = QApplication.instance()
        if app:
            act_quit.triggered.connect(app.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _build_no_tray_quit_button(self) -> None:
        """Adds a Quit button directly to the dashboard while no system tray is available."""
        btn = QPushButton(t("tray.menu.quit"))
        app = QApplication.instance()
        if app:
            btn.clicked.connect(app.quit)
        layout = self.dashboard.layout()
        if isinstance(layout, QVBoxLayout):
            layout.addWidget(btn)
            self._no_tray_quit_btn = btn

    def _retry_tray(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_retry_timer.stop()
            self.tray.show()
            if self._no_tray_quit_btn is not None:
                self._no_tray_quit_btn.deleteLater()
                self._no_tray_quit_btn = None
            return
        self._tray_retry_count += 1
        if self._tray_retry_count >= self.TRAY_RETRY_LIMIT:
            self._tray_retry_timer.stop()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_dashboard()

    def _show_dashboard(self):
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    @Slot(str)
    def on_text_ready(self, text: str) -> None:
        from core.text_injector import inject_text
        self.dashboard.set_last_transcript(text)
        method = self.settings.get("injection_method", "clipboard")
        inject_text(text, log_callback=self.dashboard.append_log_entry, injection_method=method)

    @Slot()
    def on_hotkey_pressed(self):
        if self.transcription_worker and not self.transcription_worker.is_ready:
            if self.osd:
                self.osd.setStateError(STATE_LOADING if self.transcription_worker.is_loading else MSG_MODEL_NOT_FOUND)
            return
        if self.osd:
            self.osd.setStateRecording()
        self.set_recording(True)
        if self.audio_worker:
            self.audio_worker.start_recording()

    @Slot()
    def on_hotkey_released(self):
        self.set_recording(False)
        if self.audio_worker:
            self.audio_worker.stop_recording()

    # ----------------------------------------------------------------- public
    def set_recording(self, active: bool):
        if active:
            self.tray.setIcon(self._icon_rec)
            self.tray.setToolTip(f"{APP_NAME} — {t(STATE_LISTENING)}")
            self.dashboard.set_status(STATE_LISTENING, "ERR")
        else:
            self._resolve_idle_status()
            self.dashboard.update_level(0.0)

    def _resolve_idle_status(self) -> None:
        self.tray.setIcon(self._icon_idle)
        if self._mic_unavailable:
            self.tray.setToolTip(f"{APP_NAME} — {t(MSG_MIC_UNAVAILABLE)}")
            self.dashboard.set_status(MSG_MIC_UNAVAILABLE, "ERR")
        elif self.transcription_worker and not self.transcription_worker.is_ready:
            key, level = ((STATE_LOADING, "IDLE") if self.transcription_worker.is_loading
                          else (MSG_MODEL_NOT_FOUND, "WARN"))
            self.tray.setToolTip(f"{APP_NAME} — {t(key)}")
            self.dashboard.set_status(key, level)
        else:
            self.tray.setToolTip(f"{APP_NAME} — {t(STATE_READY)}")
            self.dashboard.set_status(STATE_READY, "OK")

    @Slot()
    def on_mic_unavailable(self) -> None:
        self._mic_unavailable = True
        self.dashboard.set_status(MSG_MIC_UNAVAILABLE, "ERR")

    @Slot()
    def on_mic_available(self) -> None:
        self._mic_unavailable = False
        self._resolve_idle_status()
