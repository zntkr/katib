import sys
import os
import io
import typing
import logging
from logging.handlers import RotatingFileHandler
import traceback
import pprint
from pathlib import Path
from PySide6.QtWidgets import QApplication
from core.settings import (
    APP_NAME, MSG_MODEL_NOT_FOUND, MSG_MIC_UNAVAILABLE,
    STATE_RECORDING, STATE_PROCESSING, STATE_LISTENING, STATE_READY,
)
import PySide6.QtSvg  # required for SVG plugin registration
import warnings
import signal

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"  # suppress symlink warnings
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"     # prevent tqdm crashes when there is no console
os.environ["CT2_VERBOSE"] = "-3"                     # silence all CTranslate2 (C++) hardware warnings
warnings.filterwarnings("ignore", category=UserWarning) # suppress Python (Whisper) warnings

# ── Logging System ────────────────────────────────────────────────────
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

def setup_logging():
    local_app_data = os.environ.get("LOCALAPPDATA")
    base_dir = Path(local_app_data) if local_app_data else Path.home()
    log_dir = base_dir / APP_NAME / "Logs"
    log_file = log_dir / "katib.log"

    # Prevent a Fatal Error crash if directory creation is blocked by strict system permissions.
    try:
        log_dir.mkdir(parents=True, exist_ok=True)

        handlers_list: list[logging.Handler] = [RotatingFileHandler(str(log_file), maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')]
        if sys.stdout is not None:
            handlers_list.append(logging.StreamHandler(sys.stdout))

        logging.basicConfig(
            handlers=handlers_list,
            level=logging.INFO,
            format="%(asctime)s.%(msecs)03d | %(levelname)-8s | PID:%(process)-5d | %(threadName)-22s | %(filename)s:%(lineno)-4d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    except Exception:
        # Fallback to stream-only logging if the filesystem is not writable.
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
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
                locals_str = pprint.pformat(frame.f_locals, indent=2, width=120, depth=3, compact=True)
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

# ── QApplication ─────────────────────────────────────────────────────────
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
    # ── Single-Instance Lock ──────────────────────────────────────────────
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
    from core.settings import SettingsManager

    settings_manager = SettingsManager()
    from core.i18n import set_language as _i18n_set_language, t as _t, available_languages
    _lang = settings_manager.get("app_language") or ""
    if not _lang:
        import locale
        try:
            _sys_code = (locale.getdefaultlocale()[0] or "")[:2]
        except Exception:
            _sys_code = ""
        _available = {code for _, code in available_languages()}
        _lang = _sys_code if _sys_code in _available else "en"
        settings_manager.set("app_language", _lang)
    _i18n_set_language(_lang)
    for _k in (MSG_MODEL_NOT_FOUND, MSG_MIC_UNAVAILABLE,
               STATE_RECORDING, STATE_PROCESSING, STATE_LISTENING, STATE_READY):
        if _t(_k) == _k:
            global_logger.warning("i18n: STATUS key missing in catalog: '%s'", _k)
    theme_manager.apply_theme(app)
    global_logger.info("Theme and settings loaded.")

    # Qt environment is ready — import UI module now.
    # Workers are imported deferred, after the event loop starts.
    from ui.tray_app import TrayApp

    global_logger.info("Building UI (Tray/Dashboard)...")
    tray = TrayApp(settings=settings_manager)
    app.setWindowIcon(tray._icon_idle)

    # ── Deferred Startup ──────────────────────────────────────────────────
    # show() is intentionally called at the END of _deferred_init.
    # Calling show() before all heavy imports finish blocks the main thread,
    # leaving DWM's initial white frame visible until WM_PAINT is processed (flash).

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
        audio_worker         = AudioWorker(settings=settings_manager)
        transcription_worker = TranscriptionWorker(settings=settings_manager)
        downloader_worker    = ModelDownloaderWorker(settings=settings_manager)
        osd                  = MinimalOSD()

        _workers.update(hw=hotkey_worker, aw=audio_worker,
                        tw=transcription_worker, dw=downloader_worker)

        # Give TrayApp references to the workers so UI manipulations
        # are safely routed to the main thread via QueuedConnection.
        tray.transcription_worker = transcription_worker
        tray.audio_worker = audio_worker
        tray.osd = osd

        # ---------------------------------------------------- signal wiring
        global_logger.info("Wiring signals...")

        # Key pressed/released → directly trigger TrayApp QObject slots (thread-safe)
        hotkey_worker.hotkey_pressed.connect(tray.on_hotkey_pressed)
        hotkey_worker.hotkey_released.connect(tray.on_hotkey_released)

        # OSD connections — setStateRecording is now called from inside on_hotkey_pressed (after model guard)
        audio_worker.audio_failed.connect(osd.hide_osd)
        transcription_worker.transcription_started.connect(osd.setStateProcessing)
        transcription_worker.transcription_finished.connect(osd.hide_osd)

        # Microphone hardware error → persistent dashboard status + transient OSD error
        audio_worker.mic_unavailable.connect(tray.on_mic_unavailable)

        # All worker errors → OSD + tray balloon
        audio_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))
        hotkey_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))
        transcription_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))
        transcription_worker.model_missing.connect(lambda: osd.setStateError(MSG_MODEL_NOT_FOUND))
        transcription_worker.model_missing.connect(tray.dashboard.show_model_missing_guidance)
        transcription_worker.model_loaded.connect(tray.dashboard.clear_model_missing_guidance)
        downloader_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))

        audio_worker.audio_ready.connect(transcription_worker.add_audio)

        transcription_worker.text_ready.connect(tray.on_text_ready)

        audio_worker.level_changed.connect(tray.dashboard.update_level)
        transcription_worker.status_changed.connect(tray.dashboard.set_status)
        transcription_worker.loading_state_changed.connect(tray.dashboard.set_loading_indicator)

        audio_worker.log_entry.connect(tray.dashboard.append_log_entry)
        transcription_worker.log_entry.connect(tray.dashboard.append_log_entry)
        hotkey_worker.log_entry.connect(tray.dashboard.append_log_entry)

        # Bridge UI log entries to the disk log as well.
        def _file_log_bridge(lvl, cat, msg):
            log_str = f"[{cat}] {msg}"
            if lvl in ("ERR", "WRN"):
                global_logger.error(log_str)
            else:
                global_logger.info(log_str)

        audio_worker.log_entry.connect(_file_log_bridge)
        transcription_worker.log_entry.connect(_file_log_bridge)
        hotkey_worker.log_entry.connect(_file_log_bridge)
        downloader_worker.log_entry.connect(_file_log_bridge)

        # Forward WRN log entries to OSD (3 s, only user-visible categories).
        _OSD_WRN_CATS = {"MIC", "STT", "KEY"}
        def _wrn_to_osd(lvl, cat, msg):
            if lvl == "WRN" and cat in _OSD_WRN_CATS:
                osd.setStateError(msg)

        audio_worker.log_entry.connect(_wrn_to_osd)
        transcription_worker.log_entry.connect(_wrn_to_osd)
        hotkey_worker.log_entry.connect(_wrn_to_osd)


        # Microphone change → update audio worker + clear error flag
        tray.dashboard.device_changed.connect(audio_worker.set_device)
        tray.dashboard.device_changed.connect(lambda _: tray.on_mic_available())

        # Hotkey change → update hotkey worker
        tray.dashboard.hotkey_changed.connect(hotkey_worker.set_key)
        # Pause hotkey worker during capture mode so accidental presses don't start recording.
        tray.dashboard.hotkey_capture_mode.connect(
            lambda capturing: hotkey_worker.pause() if capturing else hotkey_worker.resume()
        )

        # Model folder or compute setting changed → reload model
        tray.dashboard.model_dir_changed.connect(transcription_worker.reload_model)
        tray.dashboard.model_reload_requested.connect(transcription_worker.reload_model)

        # Device list: UI requests → AudioWorker queries → UI populates
        tray.dashboard.refresh_devices_requested.connect(audio_worker.refresh_devices)
        audio_worker.devices_ready.connect(tray.dashboard.populate_devices)
        audio_worker.refresh_devices()   # populate combo on startup
        # populate_devices finds the saved microphone and emits device_changed to call set_device.

        # Model downloader: UI → downloader → dashboard + transcription
        tray.dashboard.download_model_requested.connect(downloader_worker.start_download)
        downloader_worker.log_entry.connect(tray.dashboard.append_log_entry)
        downloader_worker.error_occurred.connect(lambda _: tray.dashboard.set_loading_indicator(False))
        downloader_worker.error_occurred.connect(lambda _: tray.dashboard.set_download_state(False))
        downloader_worker.status_changed.connect(tray.dashboard.set_status)
        downloader_worker.download_state_changed.connect(tray.dashboard.set_download_state)
        downloader_worker.download_finished.connect(tray.dashboard.on_download_complete)

        # ---------------------------------------------------- start workers
        global_logger.info("Starting worker threads...")
        transcription_worker.start()
        audio_worker.start()
        hotkey_worker.start()

        tray.dashboard.show()
        tray.dashboard.raise_()
        tray.dashboard.append_log_entry("OK", "APP", _t("app.started").format(key=settings_manager.get('hotkey', 'F9').upper()))
        global_logger.info("System ready.")

    # ----------------------------------------------------- graceful shutdown
    def shutdown():
        global_logger.info("=== Shutdown Started ===")
        tray.dashboard.append_log_entry("...", "APP", _t("app.shutting_down"))

        # Hide windows to avoid C++-side drawing errors (QBackingStore) after the event loop ends.
        for window in QApplication.topLevelWidgets():
            window.hide()
        if hasattr(tray, 'tray'):
            tray.tray.hide()

        # Send only a soft stop signal to worker threads — no wait() — to avoid
        # freezing the UI or triggering a GIL deadlock.
        if 'hw' in _workers:
            global_logger.info("Arka plan Worker thread'leri durduruluyor...")
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
    logging.shutdown()
    os._exit(0)


if __name__ == "__main__":
    main()
