import sys

# --- MİMARİ AĞ DÜZELTMESİ: Windows SSL Sertifika Deposunu Kullan ---
# Şirket proxy'lerine (Zscaler vb.) takılan sertifika hatalarını çözer.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
# -------------------------------------------------------------------
import os
import io
import typing
import logging
import queue
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
import traceback
import pprint
from pathlib import Path
from PySide6.QtWidgets import QApplication
from core.settings import (
    APP_NAME, MSG_MODEL_NOT_FOUND, MSG_MIC_UNAVAILABLE,
    STATE_PROCESSING, STATE_LISTENING, STATE_READY, get_log_dir,
)
from core.log import PrivacyFormatter, LogViewHandler, get_logger, mask_text, OK
import PySide6.QtSvg  # required for SVG plugin registration
import warnings
import signal

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"  # suppress symlink warnings
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"     # prevent tqdm crashes when there is no console
os.environ["CT2_VERBOSE"] = "-3"                     # silence all CTranslate2 (C++) hardware warnings
warnings.filterwarnings("ignore", category=UserWarning) # suppress Python (Whisper) warnings

# Logging System
class StreamToLogger(io.TextIOBase):
    """Redirects console output (print, tqdm, library errors) to the log file."""
    def __init__(self, logger: logging.Logger, level: int):
        super().__init__()
        self.logger = logger
        self.level = level

    def write(self, buf: str) -> int:
        for line in buf.rstrip().splitlines():
            if line.strip():
                self.logger.log(self.level, line.strip())
        return len(buf)

    def flush(self):
        pass

_LOG_FORMAT      = "%(asctime)s.%(msecs)03d | %(levelname)-8s | PID:%(process)-5d | %(threadName)-22s | %(name)s | %(filename)s:%(lineno)-4d | %(message)s"
_LOG_DATEFMT     = "%Y-%m-%d %H:%M:%S"
_owned_handlers: list[logging.Handler] = []  # installed by setup_logging(); replaced on a re-run
# File and console writes happen on the listener's thread, never on the thread that logs:
# a PortAudio callback must not block on disk I/O (plan 0004).
_log_queue: queue.Queue = queue.Queue()
_log_listener: QueueListener | None = None


def stop_logging() -> None:
    """Writes out everything still queued. Call before os._exit(), which skips atexit."""
    global _log_listener
    if _log_listener is not None:
        _log_listener.stop()
        _log_listener = None


def setup_logging():
    global _log_listener
    log_dir = get_log_dir()
    log_file = log_dir / "katib.log"

    root = logging.getLogger()
    stop_logging()
    for h in _owned_handlers:
        root.removeHandler(h)
        h.close()
    _owned_handlers.clear()

    handlers_list: list[logging.Handler] = []
    # Prevent a Fatal Error crash if directory creation is blocked by strict system permissions.
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers_list.append(RotatingFileHandler(str(log_file), maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'))
    except Exception:
        pass  # fall back to console-only logging if the filesystem is not writable
    # In --noconsole mode a previous run replaced sys.stdout with StreamToLogger; a console
    # handler writing to it would feed every record back into logging (plan 0004).
    if sys.stdout is not None and not isinstance(sys.stdout, StreamToLogger):
        handlers_list.append(logging.StreamHandler(sys.stdout))

    formatter = PrivacyFormatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT)
    for h in handlers_list:
        h.setFormatter(formatter)
        _owned_handlers.append(h)
    _log_listener = QueueListener(_log_queue, *handlers_list, respect_handler_level=True)
    _log_listener.start()
    queue_handler = QueueHandler(_log_queue)
    root.addHandler(queue_handler)
    _owned_handlers.append(queue_handler)
    root.setLevel(logging.INFO)
    logger = logging.getLogger(APP_NAME)

    # In --noconsole mode stdout/stderr are None. Route them to the logger instead of
    # /dev/null so library write() calls don't crash and hidden errors are captured.
    if sys.stdout is None:
        sys.stdout = typing.cast(typing.TextIO, StreamToLogger(logger, logging.INFO))
    if sys.stderr is None:
        sys.stderr = typing.cast(typing.TextIO, StreamToLogger(logger, logging.ERROR))

    # Log all unhandled exceptions globally.
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            logger.info("KeyboardInterrupt received from terminal.")
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        exception_list = traceback.format_exception(exc_type, exc_value, exc_traceback)
        exception_text = "".join(exception_list)

        # Include local variables from each frame for easier post-mortem debugging.
        log_message = [
            "Unhandled Exception:\n",
            exception_text,
            "\n" + "="*20 + " LOCALS " + "="*20 + "\n"
        ]

        tb = exc_traceback
        while tb is not None:
            frame = tb.tb_frame
            log_message.append(
                f"\n--- File: {frame.f_code.co_filename}, Line: {frame.f_lineno}, Function: {frame.f_code.co_name} ---\n"
            )
            try:
                # Limit depth and total size to keep log entries readable.
                # Strings are masked: they may hold dictated text (ADR-0004).
                # dict(): since Python 3.13 f_locals is a proxy, not a dict, and mask_text
                # would pass it through unmasked.
                locals_str = pprint.pformat(mask_text(dict(frame.f_locals)), indent=2, width=120, depth=3, compact=True)
                if len(locals_str) > 4096:
                    locals_str = locals_str[:4096] + "\n... (truncated)"
                log_message.append(locals_str)
            except Exception as e:
                log_message.append(f"<Error reading locals: {e}>")
            
            log_message.append("\n")
            tb = tb.tb_next

        logger.error("".join(log_message))

    sys.excepthook = handle_exception
    return logger

global_logger = setup_logging()
global_logger.info("=== Katib Starting ===")

# QApplication
# Qt objects (QPixmap, QIcon, QWidget, etc.) can only exist AFTER QApplication.
# Therefore all other imports come AFTER QApplication is created.


def _sigint_handler(signum, frame):
    global_logger.info("SIGINT received from terminal, shutting down...")
    app = QApplication.instance()
    if app:
        app.quit()
    else:
        sys.exit(0)

def main():
    signal.signal(signal.SIGINT, _sigint_handler)
    # Single-Instance Lock
    # Silently prevents a second launch; QSharedMemory lives for the process lifetime.
    from PySide6.QtCore import QSharedMemory
    _shared_memory = QSharedMemory("Katib_SingleInstance_Mutex")
    if not _shared_memory.create(1):
        global_logger.warning("Application already running. Blocking second launch attempt.")
        sys.exit(0)

    global_logger.info("Starting QApplication...")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # The Fusion style can override CSS colors; we leave it disabled.

    from ui.theme import theme_manager
    from core.settings import SettingsManager, DEFAULT_DOWNLOAD_PARENT, migrate_legacy_data, first_run_speech_settings
    from core.models import ModelProvider

    migrate_legacy_data()  # must run before SettingsManager reads settings.json
    settings_manager = SettingsManager()
    model_provider = ModelProvider(base_download_dir=DEFAULT_DOWNLOAD_PARENT, active_model_path=settings_manager.get("model_dir"))
    from core.i18n import (set_language as _i18n_set_language, t as _t, available_languages,
                           resolve_app_language, system_language_code)
    if settings_manager.first_run:
        # A new install starts in the computer's language; existing users keep theirs.
        settings_manager.set_many(first_run_speech_settings(system_language_code()))
    _saved_lang = settings_manager.get("app_language") or ""
    _lang = resolve_app_language(_saved_lang, {code for _, code in available_languages()})
    if _lang != _saved_lang:
        settings_manager.set("app_language", _lang)  # the settings dialog shows the stored value
    _i18n_set_language(_lang)
    if _lang in {"ar", "fa", "ur"}:
        from PySide6.QtCore import Qt
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    for _k in (MSG_MODEL_NOT_FOUND, MSG_MIC_UNAVAILABLE,
               STATE_PROCESSING, STATE_LISTENING, STATE_READY):
        if _t(_k) == _k:
            global_logger.warning("i18n: STATUS key missing in catalog: '%s'", _k)
    theme_manager.apply_theme(app)
    global_logger.info("Theme and settings loaded.")

    from ui.tray_app import TrayApp

    global_logger.info("Building UI (tray, settings window)...")
    tray = TrayApp(settings=settings_manager, model_provider=model_provider)
    window = tray.settings_window
    app.setWindowIcon(tray.icon_idle)

    # ADR-0004: every "Katib.<COMPONENT>" logger also feeds the log tab of the settings
    # window (setup_logging() already writes them to the file, without transcript text).
    log_view = LogViewHandler()
    log_view.bridge.entry.connect(window.append_log_entry)
    logging.getLogger(APP_NAME).addHandler(log_view)
    app_log = get_logger("APP")

    _workers = {}

    def _deferred_init():
        global_logger.info("Starting deferred initialization...")
        from workers.hotkey_worker import HotkeyWorker
        from workers.audio_worker import AudioWorker
        from workers.transcription_worker import TranscriptionWorker
        from workers.model_downloader_worker import ModelDownloaderWorker
        from ui.osd import MinimalOSD

        global_logger.info("Creating workers...")
        hotkey_worker        = HotkeyWorker(settings=settings_manager, key=settings_manager.get("hotkey", "F9"))
        from core.portaudio_source import PortAudioSource
        
        audio_source         = PortAudioSource()
        audio_worker         = AudioWorker(settings=settings_manager, audio_source=audio_source)
        transcription_worker = TranscriptionWorker(settings=settings_manager, model_provider=model_provider)
        downloader_worker    = ModelDownloaderWorker(settings=settings_manager)
        osd                  = MinimalOSD()

        _workers.update(hw=hotkey_worker, aw=audio_worker,
                        tw=transcription_worker, dw=downloader_worker)

        tray.attach_workers(audio_worker=audio_worker, transcription_worker=transcription_worker, osd=osd)

        # ---------------------------------------------------- signal wiring
        global_logger.info("Wiring signals...")

        # Key pressed/released → directly trigger TrayApp QObject slots (thread-safe)
        hotkey_worker.hotkey_pressed.connect(tray.on_hotkey_pressed)
        hotkey_worker.hotkey_released.connect(tray.on_hotkey_released)

        # OSD connections — setStateRecording is now called from inside on_hotkey_pressed (after model guard)
        audio_worker.audio_failed.connect(osd.hide_osd)
        transcription_worker.transcription_started.connect(osd.setStateProcessing)
        transcription_worker.transcription_finished.connect(osd.hide_osd)

        # Microphone hardware error → persistent tray status + transient OSD error
        audio_worker.mic_unavailable.connect(tray.on_mic_unavailable)
        # Binary Armor: signal exactly 0.0 for > 1.5 s while recording → the mic is muted
        audio_worker.muted_detected.connect(lambda: osd.setStateError("osd.mic_muted"))

        # All worker errors → OSD
        audio_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))
        hotkey_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))
        transcription_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))
        transcription_worker.model_missing.connect(lambda: osd.setStateError(MSG_MODEL_NOT_FOUND))
        transcription_worker.model_missing.connect(tray.on_model_missing)
        transcription_worker.model_loaded.connect(window.on_model_loaded)
        downloader_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))

        audio_worker.audio_ready.connect(transcription_worker.add_audio)
        # Long dictations: finished sentences are transcribed while the user is still speaking,
        # and a hands-free dictation (key tapped, not held) ends when the speaker stops (plan 0014).
        audio_worker.recording_started.connect(transcription_worker.begin_dictation)
        audio_worker.partial_audio.connect(transcription_worker.add_partial)
        transcription_worker.speech_ended.connect(tray.on_speech_ended)

        transcription_worker.text_ready.connect(tray.on_text_ready)

        audio_worker.level_changed.connect(tray.on_level_changed)
        audio_worker.level_changed.connect(osd.update_level)
        # Status: workers report facts, TrayApp decides what the tray shows (single owner)
        transcription_worker.status_changed.connect(tray.on_model_status)
        transcription_worker.transcription_started.connect(tray.on_transcription_started)
        transcription_worker.transcription_finished.connect(tray.on_transcription_finished)
        transcription_worker.loading_state_changed.connect(window.set_loading_indicator)

        # Microphone change → update audio worker + clear error flag
        window.device_changed.connect(audio_worker.set_device)
        window.device_changed.connect(lambda _: tray.on_mic_available())

        # Hotkey change → update hotkey worker
        window.hotkey_changed.connect(hotkey_worker.set_key)
        # Pause hotkey worker during capture mode so accidental presses don't start recording.
        window.hotkey_capture_mode.connect(
            lambda capturing: hotkey_worker.pause() if capturing else hotkey_worker.resume()
        )

        # Model folder changed → reload model
        def _on_model_dir_changed(path):
            model_provider.active_model_path = path
            transcription_worker.reload_model()

        window.model_dir_changed.connect(_on_model_dir_changed)

        # Live facts on the dictation tab: how loud the last recording was, how long the model took
        audio_worker.recording_analysed.connect(window.show_last_recording)
        transcription_worker.dictation_timed.connect(window.show_last_dictation)
        transcription_worker.dictation_timed.connect(tray.on_dictation_timed)  # release → paste log line

        # Device list: AudioWorker queries → the settings window shows it and reports the
        # microphone in use through device_changed.
        audio_worker.devices_ready.connect(window.populate_devices)
        audio_worker.refresh_devices()   # fill the list on startup

        # Model downloader: settings window → downloader → settings window + transcription
        window.download_model_requested.connect(downloader_worker.start_download)
        downloader_worker.error_occurred.connect(lambda _: window.set_download_state(False))
        downloader_worker.status_changed.connect(tray.on_download_status)
        downloader_worker.download_state_changed.connect(window.set_download_state)
        downloader_worker.download_state_changed.connect(tray.on_download_state)
        downloader_worker.download_finished.connect(window.on_download_complete)

        window.language_change_requested.connect(tray.apply_language)
        window.help_requested.connect(tray.show_help)

        # ---------------------------------------------------- start workers
        global_logger.info("Starting worker threads...")
        transcription_worker.start()
        audio_worker.start()
        hotkey_worker.start()

        # No window opens at startup: the tray icon and the pill are the interface (ADR-0012).
        # The settings window opens itself only when there is no model to dictate with.
        app_log.log(OK, _t("app.started").format(key=settings_manager.get('hotkey', 'F9').upper()))
        global_logger.info("System ready.")

    # ----------------------------------------------------- graceful shutdown
    def shutdown():
        global_logger.info("=== Shutdown Started ===")
        app_log.info(_t("app.shutting_down"))

        # Hide windows to avoid C++-side drawing errors (QBackingStore) after the event loop ends.
        for widget in QApplication.topLevelWidgets():
            widget.hide()
        tray.tray.hide()

        # Send only a soft stop signal to worker threads — no wait() — to avoid
        # freezing the UI or triggering a GIL deadlock.
        if 'hw' in _workers:
            global_logger.info("Stopping worker threads...")
            _workers['hw'].stop()
            _workers['aw'].stop()
            _workers['tw'].stop()
            

    app.aboutToQuit.connect(shutdown)

    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, _deferred_init)

    # Periodically wake the Python interpreter so the C++ event loop (app.exec)
    # does not block Python signals such as Ctrl+C (SIGINT).
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(500)

    app.exec()

    # After app.exec() returns, QTimers no longer run.
    # Give workers the 250 ms they need to finish.
    # Waiting (wait) or force-killing (terminate) C++ QThreads from Python causes
    # permanent hangs, so we terminate at OS level immediately instead.
    import time
    time.sleep(0.25)
    global_logger.info("Clean shutdown (os._exit).")
    stop_logging()
    logging.shutdown()
    os._exit(0)


if __name__ == "__main__":
    main()
