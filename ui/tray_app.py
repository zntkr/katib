import time
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtCore import QObject, Qt, Slot, QTimer

from core.settings import (
    APP_NAME, MSG_MIC_UNAVAILABLE, MSG_MODEL_NOT_FOUND, STATE_LISTENING, STATE_LOADING,
    STATE_PROCESSING,
)
from core.chime import chime
from core.i18n import t, set_language
from core.log import get_logger, OK
from core.text_injector import inject_text
from ui.utils import colorize_svg_icon
from ui.theme import theme_manager
from ui.icons import ICN_MIC
from ui.settings_window import SettingsWindow

if TYPE_CHECKING:
    from workers.audio_worker import AudioWorker
    from ui.help_window import HelpWindow
    from ui.osd import MinimalOSD
    from workers.transcription_worker import TranscriptionWorker

_log = get_logger("APP")


def _log_dictation_latency(released_at: float, timing: tuple[float, float] | None) -> None:
    """The number the user feels: key release → text pasted (plan 0012)."""
    elapsed_ms = (time.perf_counter() - released_at) * 1000.0
    detail = ""
    if timing is not None:
        audio_seconds, model_seconds = timing
        detail = f" (audio {audio_seconds:.1f} s, model {model_seconds * 1000.0:.0f} ms)"
    _log.log(OK, f"Dictation done: release->paste {elapsed_ms:.0f} ms{detail}")


class TrayApp(QObject):
    """The tray icon and its menu. Owns the settings window and decides which status the
    tray shows (ADR-0012). Instantiated AFTER QApplication is created in main.py."""

    _RTL_LANGS = {"ar", "fa", "ur"}
    TRAY_RETRY_INTERVAL_MS = 5000
    TRAY_RETRY_LIMIT       = 60  # give up after 5 minutes
    TAP_SECONDS            = 0.8  # a key press shorter than this is a tap, not a hold

    def __init__(self, settings, model_provider, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings
        self.model_provider = model_provider

        self.audio_worker: 'AudioWorker | None' = None
        self.transcription_worker: 'TranscriptionWorker | None' = None
        self.osd: 'MinimalOSD | None' = None
        # Facts the status is derived from; only _resolve_status() writes it.
        self._recording: bool = False
        self._processing: bool = False
        self._mic_unavailable: bool = False
        self._download_notice: tuple[str, str] | None = None
        self._downloading: bool = False
        self._model_status: tuple[str, str] = (STATE_LOADING, "IDLE")
        self._last_transcript: str | None = None
        self._help_window: 'HelpWindow | None' = None
        # Key release of the dictation in flight and its model timing: the one number the user
        # feels is release → paste (plan 0012). Cleared when the dictation ends either way.
        self._released_at: float | None = None
        self._dictation_timing: tuple[float, float] | None = None  # seconds of audio, seconds of model
        # One key, two ways to dictate: hold it and speak, or tap it and speak hands-free.
        self._pressed_at: float | None = None
        self._hands_free: bool = False
        self._swallow_release: bool = False  # the release of the tap that ended a hands-free dictation
        self._transcript_parts: list[str] = []

        p = theme_manager.palette
        self.icon_idle = colorize_svg_icon(ICN_MIC, p["CLR_TEXT_MUTED"], size=64)
        self._icon_rec  = colorize_svg_icon(ICN_MIC, p["CLR_ERR"], size=64)

        self.settings_window = SettingsWindow(settings=self.settings, model_provider=self.model_provider, icon=self.icon_idle)

        # The tray icon object always exists so icon/tooltip updates never need a
        # guard; it is only shown once the OS actually provides a system tray.
        self._build_tray()
        self._tray_retry_count = 0
        self._tray_retry_timer = QTimer(self)
        self._tray_retry_timer.setInterval(self.TRAY_RETRY_INTERVAL_MS)
        self._tray_retry_timer.timeout.connect(self._retry_tray)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            # e.g. autostart at login before Explorer has created the taskbar. Without a tray
            # icon the settings window is the only way to reach Katib, and to quit it.
            self.settings_window.set_tray_available(False)
            self.settings_window.show_tab("app")
            self.settings_window.show()
            self._tray_retry_timer.start()
        self._resolve_status()

    # ------------------------------------------------------------------ tray
    @Slot(str)
    def apply_language(self, lang_code: str) -> None:
        set_language(lang_code)
        direction = Qt.LayoutDirection.RightToLeft if lang_code in self._RTL_LANGS else Qt.LayoutDirection.LeftToRight
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setLayoutDirection(direction)
        self.tray.hide()
        self.tray.deleteLater()
        self._build_tray()
        self._resolve_status()  # the rebuilt icon must show the current state (plan 0003)
        self.settings_window.rebuild()
        if self.osd:
            self.osd.refresh_language()
        if self._help_window is not None:
            self._help_window.close()
            self._help_window = None  # built again, in the new language, when next opened

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self.icon_idle)  # icon and tooltip are set by _resolve_status()

        self._menu = QMenu()
        act_settings = self._menu.addAction(t("tray.menu.settings"))
        act_help = self._menu.addAction(t("tray.menu.user_guide"))
        self._act_copy = self._menu.addAction(t("tray.menu.copy_transcript"))
        self._act_copy.setEnabled(self._last_transcript is not None)
        self._menu.addSeparator()
        act_quit = self._menu.addAction(t("tray.menu.quit"))

        act_settings.triggered.connect(self.show_settings)
        act_help.triggered.connect(self.show_help)
        self._act_copy.triggered.connect(self.copy_last_transcript)
        app = QApplication.instance()
        if app:
            act_quit.triggered.connect(app.quit)

        self.tray.setContextMenu(self._menu)
        self.tray.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _retry_tray(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_retry_timer.stop()
            self.tray.show()
            self.settings_window.set_tray_available(True)
            return
        self._tray_retry_count += 1
        if self._tray_retry_count >= self.TRAY_RETRY_LIMIT:
            self._tray_retry_timer.stop()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_settings()

    @Slot()
    def show_settings(self) -> None:
        self.settings_window.show()

    @Slot()
    def show_help(self) -> None:
        from ui.help_window import HelpWindow
        if self._help_window is None:
            self._help_window = HelpWindow(settings=self.settings)
        self._help_window.show()
        self._help_window.raise_()
        self._help_window.activateWindow()

    @Slot()
    def copy_last_transcript(self) -> None:
        if self._last_transcript:
            QApplication.clipboard().setText(self._last_transcript)

    @Slot(str)
    def on_text_ready(self, text: str) -> None:
        # A hands-free dictation arrives in pieces; "copy last dictation" means all of them.
        self._transcript_parts.append(text)
        self._last_transcript = " ".join(self._transcript_parts)
        self._act_copy.setEnabled(True)
        # Taken before the paste: inject_text() runs processEvents(), which can deliver
        # transcription_finished (it clears both) before the paste returns.
        released_at, timing = self._released_at, self._dictation_timing
        self._released_at = self._dictation_timing = None
        inject_text(text, injection_method=self.settings.get("injection_method", "clipboard"))
        if released_at is not None:
            _log_dictation_latency(released_at, timing)

    @Slot(float, float)
    def on_dictation_timed(self, audio_seconds: float, model_seconds: float) -> None:
        """TranscriptionWorker.dictation_timed; arrives before text_ready (same thread, queued)."""
        self._dictation_timing = (audio_seconds, model_seconds)

    @Slot()
    def on_hotkey_pressed(self):
        if self._hands_free:  # the second tap: the user says they are done
            self._swallow_release = True
            self._end_dictation()
            return
        if self.transcription_worker and not self.transcription_worker.is_ready:
            if self.osd:
                self.osd.setStateError(STATE_LOADING if self.transcription_worker.is_loading else MSG_MODEL_NOT_FOUND)
            return
        if self.osd:
            self.osd.setStateRecording()
        self._released_at = None  # a dropped recording must not time the next one
        self._dictation_timing = None
        self._pressed_at = time.monotonic()
        self.set_recording(True)
        if self.audio_worker:
            self.audio_worker.start_recording()
        if self._recording:  # still true: the microphone opened
            chime("start")

    @Slot()
    def on_hotkey_released(self):
        """Held key: the release ends the dictation. Short tap: it goes on hands-free until
        the next tap or until the speaker stops (on_speech_ended)."""
        if self._swallow_release:
            self._swallow_release = False
            return
        tapped = (self._recording and self._pressed_at is not None
                  and time.monotonic() - self._pressed_at < self.TAP_SECONDS)
        self._pressed_at = None
        if tapped:
            self._set_hands_free(True)
        else:
            self._end_dictation()

    @Slot()
    def on_speech_ended(self) -> None:
        """TranscriptionWorker.speech_ended: a hands-free dictation ends on its own."""
        if self._hands_free:
            self._end_dictation()

    def _set_hands_free(self, active: bool) -> None:
        self._hands_free = active
        if self.transcription_worker:
            self.transcription_worker.hands_free = active

    def _end_dictation(self) -> None:
        self._set_hands_free(False)
        was_recording = self._recording
        if was_recording:
            self._released_at = time.perf_counter()
        self.set_recording(False)
        if self.audio_worker:
            self.audio_worker.stop_recording()
        if was_recording:
            chime("end")  # after the microphone closed: the tone is not part of the recording

    @Slot(float)
    def on_level_changed(self, value: float) -> None:
        """AudioWorker.level_changed. A level that arrives after the recording stopped is dropped."""
        self.settings_window.update_level(value if self._recording else 0.0)

    @Slot()
    def on_model_missing(self) -> None:
        self.settings_window.show_model_missing_guidance()

    # ----------------------------------------------------------------- public
    def attach_workers(self, audio_worker: 'AudioWorker', transcription_worker: 'TranscriptionWorker',
                       osd: 'MinimalOSD') -> None:
        """Workers are created after TrayApp (deferred init), so they are attached here."""
        self.audio_worker = audio_worker
        self.transcription_worker = transcription_worker
        self.osd = osd

    def set_recording(self, active: bool):
        self._recording = active
        if not active:
            self.settings_window.update_level(0.0)
        elif not self._downloading:
            self._download_notice = None  # a finished download outcome; keep "Downloading..." (plan 0003)
        self._resolve_status()

    def _resolve_status(self) -> None:
        """The single writer of the tray icon and tooltip. First match wins."""
        if self._recording:
            key = STATE_LISTENING
        elif self._processing:
            key = STATE_PROCESSING
        elif self._download_notice is not None:
            key = self._download_notice[0]
        elif self._mic_unavailable:
            key = MSG_MIC_UNAVAILABLE
        else:
            key = self._model_status[0]
        self.tray.setIcon(self._icon_rec if self._recording else self.icon_idle)
        self.tray.setToolTip(f"{APP_NAME} — {t(key)}")

    @Slot(str, str)
    def on_model_status(self, key: str, level: str) -> None:
        """TranscriptionWorker.status_changed: no model / loading / ready / model error."""
        self._model_status = (key, level)
        self._download_notice = None  # newer than any download outcome
        self._resolve_status()

    @Slot(str, str)
    def on_download_status(self, key: str, level: str) -> None:
        """ModelDownloaderWorker.status_changed: progress and outcome of a model download."""
        self._download_notice = (key, level)
        self._resolve_status()

    @Slot(bool)
    def on_download_state(self, active: bool) -> None:
        """ModelDownloaderWorker.download_state_changed: whether a download is running."""
        self._downloading = active

    @Slot()
    def on_transcription_started(self) -> None:
        self._processing = True
        self._resolve_status()

    @Slot()
    def on_transcription_finished(self) -> None:
        self._processing = False
        self._released_at = None  # no speech or an error: nothing was pasted, nothing to time
        self._dictation_timing = None
        self._transcript_parts = []  # the dictation is complete; the next text starts a new one
        self._resolve_status()

    @Slot()
    def on_mic_unavailable(self) -> None:
        self._mic_unavailable = True
        self._recording = False  # a recording cannot start or continue without a microphone
        self._set_hands_free(False)
        self._resolve_status()

    @Slot()
    def on_mic_available(self) -> None:
        self._mic_unavailable = False
        self._resolve_status()
