from typing import TYPE_CHECKING
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtCore import QObject, Slot, QTimer

from core.settings import APP_NAME, MSG_MIC_UNAVAILABLE, MSG_MODEL_NOT_FOUND, STATE_LISTENING, STATE_READY
from core.i18n import t
from PySide6.QtGui import QIcon
from ui.utils import colorize_svg_icon
from ui.theme import theme_manager
from ui.icons import ICN_MIC
from ui.control_center import ControlCenterWindow

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

        self.control_center = ControlCenterWindow(settings=self.settings, model_provider=self.model_provider)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._build_tray()
        else:
            self._build_no_tray_quit_button()

    _RTL_LANGS = {"ar", "fa", "ur"}

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
        if hasattr(self, 'tray'):
            self.tray.hide()
            self.tray.deleteLater()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._build_tray()
        # self.control_center._refresh_language_tooltips()  # Need to ensure control_center supports this or ignore
        if self.osd:
            self.osd.refresh_language()
        QTimer.singleShot(0, self._reopen_settings_after_language_change)

    def _reopen_settings_after_language_change(self) -> None:
        was_visible = self.control_center.isVisible()
        if was_visible:
            self.control_center.close()
            self.control_center.show()

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self._icon_idle)
        self.tray.setToolTip(f"{APP_NAME} — {t(STATE_READY)}")

        menu = QMenu()
        act_panel = menu.addAction(t("tray.menu.settings"))
        act_help  = menu.addAction(t("tray.menu.user_guide"))
        menu.addSeparator()
        act_quit  = menu.addAction(t("tray.menu.quit"))

        act_panel.triggered.connect(self._show_control_center)
        act_help.triggered.connect(self._open_help)
        app = QApplication.instance()
        if app:
            act_quit.triggered.connect(app.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _build_no_tray_quit_button(self) -> None:
        pass # Without a dashboard, there's nowhere to put this if there's no tray. Wait, maybe put it in control center.

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_control_center()

    def _show_control_center(self):
        self.control_center.show()
        self.control_center.raise_()
        self.control_center.activateWindow()

    def _open_help(self):
        from ui.help_window import HelpWindow
        if not hasattr(self, "_help_window"):
            self._help_window = HelpWindow(settings=self.settings)
        self._help_window.show()

    @Slot(str)
    def on_text_ready(self, text: str) -> None:
        from core.text_injector import inject_text
        method = self.settings.get("injection_method", "clipboard")
        inject_text(text, log_callback=self.control_center.append_log_entry, injection_method=method)

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
        else:
            self.tray.setIcon(self._icon_idle)
            if self._mic_unavailable:
                self.tray.setToolTip(f"{APP_NAME} — {t(MSG_MIC_UNAVAILABLE)}")
            elif self.transcription_worker and not self.transcription_worker.is_ready:
                self.tray.setToolTip(f"{APP_NAME} — {t(MSG_MODEL_NOT_FOUND)}")
            else:
                self.tray.setToolTip(f"{APP_NAME} — {t(STATE_READY)}")

    @Slot()
    def on_mic_unavailable(self) -> None:
        self._mic_unavailable = True

    @Slot()
    def on_mic_available(self) -> None:
        self._mic_unavailable = False
