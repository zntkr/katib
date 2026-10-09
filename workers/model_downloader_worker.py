import os
import shutil
import threading
import time
from collections import deque
from pathlib import Path
from PySide6.QtCore import Signal
from workers.base_worker import BaseWorker
from core.log import get_logger, OK
from core.settings import DEFAULT_DOWNLOAD_PARENT, WHISPER_MODELS, STATE_LOADING


_log = get_logger("DL")

# huggingface_hub reports progress once per chunk it reads. With its 10 MB default a steady
# 6 MB/s connection shows a speed that flips between 4 and 6 MB/s. Measured 2026-10-09 with
# the tiny model: 1 MB chunks download just as fast and report about three times a second.
CHUNK_BYTES = 1024 * 1024
SPEED_WINDOW_S = 5.0      # the speed shown is the average over this long
REPORT_INTERVAL_S = 0.25


class DownloadProgress:
    """Bytes done, bytes expected and the recent speed of one download. The library downloads
    several files at once, so advance() is called from several threads."""

    def __init__(self, on_progress, clock=time.monotonic):
        self._on_progress = on_progress          # (done, total, bytes per second)
        self._clock = clock
        self._lock = threading.Lock()
        self._done = 0
        self._samples = deque([(clock(), 0)])    # (time, bytes done by then)
        self._last_report = float("-inf")

    def advance(self, n: int, total: int) -> None:
        with self._lock:
            now = self._clock()
            self._done += n
            self._samples.append((now, self._done))
            # Keep one sample at or before the start of the window to measure from.
            while len(self._samples) > 1 and self._samples[1][0] <= now - SPEED_WINDOW_S:
                self._samples.popleft()
            if now - self._last_report < REPORT_INTERVAL_S:
                return
            self._last_report = now
            since, done_then = self._samples[0]
            speed = (self._done - done_then) / (now - since) if now > since else 0.0
            done = self._done
        self._on_progress(done, total, speed)


def progress_bar_class(progress: DownloadProgress):
    """The class snapshot_download reports through (its tqdm_class). The library makes two
    bars from it, one counting bytes (unit "B") and one counting files; only bytes count here."""
    from tqdm import tqdm

    class _Bar(tqdm):
        def __init__(self, *args, **kwargs):
            self._counts_bytes = kwargs.get("unit") == "B"
            kwargs["disable"] = True   # never drawn: the packaged app has no console
            super().__init__(*args, **kwargs)

        def update(self, n=1):
            if self._counts_bytes and n:
                # The library raises .total as it learns each file's size; 0 until then.
                progress.advance(n, self.total or 0)
            return super().update(n)

    return _Bar


class ModelDownloaderWorker(BaseWorker):
    download_finished      = Signal(str)        # final model dir path (on success)
    status_changed         = Signal(str, str)   # text, level — "OK"|"ERR"|"INFO"
    download_state_changed = Signal(bool)       # True=started, False=finished/error
    # bytes done, bytes expected (0 = not known yet), bytes per second. float: a Qt int is 32-bit.
    download_progress      = Signal(float, float, float)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._target_parent: Path = DEFAULT_DOWNLOAD_PARENT
        self._repo_id: str = ""

    def stop(self) -> None:
        pass  # Downloader is killed at OS level via os._exit

    # ---------------------------------------------------------- public control
    def start_download(self, target_parent: str, repo_id: str) -> None:
        if self.isRunning():
            _log.warning("Download already in progress.")
            return
        self._target_parent = Path(target_parent)
        self._repo_id = repo_id
        self.start()

    # ------------------------------------------------------------------ QThread
    def run(self) -> None:
        from huggingface_hub import snapshot_download, constants
        # See CHUNK_BYTES. This is an internal of the library: if a later version stops reading
        # it the download is unaffected and only the speed shown gets jumpy again
        # (tests/test_model_downloader_worker.py::TestLibraryContract).
        constants.DOWNLOAD_CHUNK_SIZE = CHUNK_BYTES

        target_parent = self._target_parent
        target_parent.mkdir(parents=True, exist_ok=True)

        # PRE-FLIGHT DISK CHECK
        # For unknown / external models, assume 4 GB as a safe upper bound.
        required_space_bytes = 4 * 1024**3
        for model_info in WHISPER_MODELS.values():
            if model_info["repo_id"] == self._repo_id:
                required_space_bytes = model_info.get("req_bytes", required_space_bytes)
                break

        free_space_bytes = shutil.disk_usage(target_parent).free

        if free_space_bytes < required_space_bytes:
            req_gb = required_space_bytes / (1024**3)
            free_gb = free_space_bytes / (1024**3)
            
            user_msg = f"Not enough disk space! (Required: {req_gb:.1f} GB, Free: {free_gb:.1f} GB)"

            _log.error(user_msg)
            self.error_occurred.emit("osd.dl_no_space")
            self.status_changed.emit("status.disk_full", "ERR")
            self.download_state_changed.emit(False)
            return
        # ───────────────────────────────────────────────────────────────

        final_dir_name = self._repo_id.split("/")[-1]
        final_dir = target_parent / final_dir_name
        temp_dir  = target_parent / f".temp_{final_dir_name}"

        # Clean up any leftover temp directory from a previous incomplete download.
        if temp_dir.exists():
            _log.info("Cleaning up previous incomplete download...")
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.download_state_changed.emit(True)
        self.status_changed.emit("status.downloading_model", "INFO")
        _log.info(f"Source: {self._repo_id}")
        _log.info("Download started, please wait...")

        try:
            snapshot_download(
                repo_id=self._repo_id,
                local_dir=str(temp_dir),
                local_dir_use_symlinks=False,
                tqdm_class=progress_bar_class(DownloadProgress(self.download_progress.emit)),
            )

            # Atomic rename: only move to the target directory once the download is complete.
            if final_dir.exists():
                # Back up the existing model, put the new one in place, then delete the backup.
                backup_dir = target_parent / f".old_{final_dir_name}"
                if backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)
                os.rename(str(final_dir), str(backup_dir))
                os.rename(str(temp_dir), str(final_dir))
                shutil.rmtree(str(backup_dir), ignore_errors=True)
            else:
                os.rename(str(temp_dir), str(final_dir))

            _log.log(OK, f"Download complete → {final_dir}")
            self.status_changed.emit(STATE_LOADING, "OK")
            self.download_state_changed.emit(False)
            self.download_finished.emit(str(final_dir))

        except Exception as e:
            _log.exception("Model downloader encountered an error:")

            # Rollback: delete the incomplete temp directory.
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    _log.info("Rollback: temporary files cleaned up.")
                except Exception:
                    _log.warning("Temporary files could not be deleted")

            err_msg = str(e)
            if "No space left" in err_msg or "Disk full" in err_msg:
                user_msg = "Not enough disk space! Please free up space and try again."
                osd_key = "osd.dl_no_space"
            elif "404" in err_msg or "Repository Not Found" in err_msg:
                user_msg = "Model not found! Please check the model name."
                osd_key = "osd.dl_model_not_found"
            elif "Connection" in err_msg or "MaxRetryError" in err_msg:
                user_msg = "Internet connection lost."
                osd_key = "osd.dl_no_internet"
            else:
                user_msg = "Download failed. Please try again."
                osd_key = "osd.dl_failed"
                _log.error(f"Detailed Error: {err_msg}")

            _log.error(user_msg)
            self.error_occurred.emit(osd_key)
            self.status_changed.emit("status.download_error", "ERR")
            self.download_state_changed.emit(False)
