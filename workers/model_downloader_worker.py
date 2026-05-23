import os
import shutil
from pathlib import Path
from PySide6.QtCore import Signal
from workers.base_worker import BaseWorker
from core.settings import DEFAULT_DOWNLOAD_PARENT, WHISPER_MODELS


class ModelDownloaderWorker(BaseWorker):
    download_finished      = Signal(str)        # final model dir path (on success)
    status_changed         = Signal(str, str)   # text, level — "OK"|"ERR"|"INFO"
    download_state_changed = Signal(bool)       # True=started, False=finished/error

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
            self.log_entry.emit("WRN", "DL", "Download already in progress.")
            return
        self._target_parent = Path(target_parent)
        self._repo_id = repo_id
        self.start()

    # ------------------------------------------------------------------ QThread
    def run(self) -> None:
        from huggingface_hub import snapshot_download

        target_parent = self._target_parent
        target_parent.mkdir(parents=True, exist_ok=True)

        # ─── PRE-FLIGHT DISK CHECK ───────────────────────────────────────
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

            self.log_entry.emit("ERR", "DL", user_msg)
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
            self.log_entry.emit("...", "DL", "Cleaning up previous incomplete download...")
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.download_state_changed.emit(True)
        self.status_changed.emit("status.downloading_model", "INFO")
        self.log_entry.emit("...", "DL", f"Source: {self._repo_id}")
        self.log_entry.emit("...", "DL", "Download started, please wait...")

        try:
            snapshot_download(
                repo_id=self._repo_id,
                local_dir=str(temp_dir),
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

            self.log_entry.emit("OK", "DL", f"Download complete → {final_dir}")
            self.status_changed.emit("status.loading_model", "OK")
            self.download_state_changed.emit(False)
            self.download_finished.emit(str(final_dir))

        except Exception as e:
            # Rollback: delete the incomplete temp directory.
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    self.log_entry.emit("...", "DL", "Rollback: temporary files cleaned up.")
                except Exception:
                    self.log_entry.emit("WRN", "DL", "Temporary files could not be deleted")

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

            self.log_entry.emit("ERR", "DL", user_msg)
            self.error_occurred.emit(osd_key)
            self.status_changed.emit("status.download_error", "ERR")
            self.download_state_changed.emit(False)
