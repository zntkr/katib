from typing import TYPE_CHECKING
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtCore import QObject, Slot

from core.settings import APP_NAME, MSG_MIC_UNAVAILABLE, MSG_MODEL_NOT_FOUND, STATE_LISTENING, STATE_READY
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

    def __init__(self, settings, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings

        self.audio_worker: 'AudioWorker | None' = None
        self.transcription_worker: 'TranscriptionWorker | None' = None
        self.osd: 'MinimalOSD | None' = None
        self._mic_unavailable: bool = False

        p = theme_manager.palette
        self._icon_idle = colorize_svg_icon(ICN_MIC, p["CLR_TEXT_MUTED"], size=64)
        self._icon_rec  = colorize_svg_icon(ICN_MIC, p["CLR_ERR"], size=64)

        self.dashboard = DashboardWindow(settings=self.settings, icon_idle=self._icon_idle)
        self._build_tray()

    # ------------------------------------------------------------------ tray
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
        self.tray.show()

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
        inject_text(text, log_callback=self.dashboard.append_log_entry)

    @Slot()
    def on_hotkey_pressed(self):
        if self.transcription_worker and not self.transcription_worker.is_ready:
            if self.osd:
                self.osd.setStateError(MSG_MODEL_NOT_FOUND)
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
            self.tray.setIcon(self._icon_idle)
            if self._mic_unavailable:
                self.tray.setToolTip(f"{APP_NAME} — {t(MSG_MIC_UNAVAILABLE)}")
                self.dashboard.set_status(MSG_MIC_UNAVAILABLE, "ERR")
            elif self.transcription_worker and not self.transcription_worker.is_ready:
                self.tray.setToolTip(f"{APP_NAME} — {t(MSG_MODEL_NOT_FOUND)}")
                self.dashboard.set_status(MSG_MODEL_NOT_FOUND, "WARN")
            else:
                self.tray.setToolTip(f"{APP_NAME} — {t(STATE_READY)}")
                self.dashboard.set_status(STATE_READY, "OK")
            self.dashboard.update_level(0.0)

    @Slot()
    def on_mic_unavailable(self) -> None:
        self._mic_unavailable = True
        self.dashboard.set_status(MSG_MIC_UNAVAILABLE, "ERR")

    @Slot()
    def on_mic_available(self) -> None:
        self._mic_unavailable = False
        if self.transcription_worker and not self.transcription_worker.is_ready:
            self.dashboard.set_status(MSG_MODEL_NOT_FOUND, "WARN")
        else:
            self.dashboard.set_status(STATE_READY, "OK")
