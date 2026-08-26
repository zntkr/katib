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
    download_progress      = Signal(int, float, float)  # percent, downloaded_mb, total_mb

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

    def _download_server_if_needed(self, target_parent: Path) -> bool:
        import requests
        import zipfile
        import io
        
        bin_dir = target_parent.parent / "bin"
        server_exe = bin_dir / "whisper-server.exe"
        if server_exe.exists():
            return True
            
        bin_dir.mkdir(parents=True, exist_ok=True)
        url = "https://github.com/ggerganov/whisper.cpp/releases/latest/download/whisper-bin-x64.zip"
        self.log_entry.emit("...", "DL", "Downloading whisper-server.exe (latest)...")
        
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                for name in z.namelist():
                    if name.endswith("whisper-server.exe"):
                        with z.open(name) as source, open(server_exe, "wb") as target:
                            shutil.copyfileobj(source, target)
                        break
            if not server_exe.exists():
                self.log_entry.emit("ERR", "DL", "whisper-server.exe not found in zip.")
                return False
            self.log_entry.emit("OK", "DL", "whisper-server.exe downloaded.")
            return True
        except Exception as e:
            self.log_entry.emit("ERR", "DL", f"Server download failed: {e}")
            return False

    # ------------------------------------------------------------------ QThread
    def run(self) -> None:
        from huggingface_hub import hf_hub_download

        target_parent = self._target_parent
        target_parent.mkdir(parents=True, exist_ok=True)

        model_info = WHISPER_MODELS.get(self._repo_id)
        if not model_info:
            self.log_entry.emit("ERR", "DL", "Unknown model requested.")
            self.error_occurred.emit("osd.dl_model_not_found")
            self.status_changed.emit("status.download_error", "ERR")
            self.download_state_changed.emit(False)
            return

        hf_repo_id = model_info["repo_id"]
        filename = model_info["filename"]
        required_space_bytes = model_info.get("req_bytes", 2 * 1024**3)

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

        final_file = target_parent / filename

        self.download_state_changed.emit(True)
        
        # 1. Download server executable if missing
        if not self._download_server_if_needed(target_parent):
            self.error_occurred.emit("osd.dl_failed")
            self.status_changed.emit("status.download_error", "ERR")
            self.download_state_changed.emit(False)
            return

        # 2. Download model
        self.status_changed.emit("status.downloading_model", "INFO")
        self.log_entry.emit("...", "DL", f"Source: {hf_repo_id}/{filename}")
        self.log_entry.emit("...", "DL", "Download started, please wait...")

        try:
            import requests
            url = f"https://huggingface.co/{hf_repo_id}/resolve/main/{filename}"
            resp = requests.get(url, stream=True, timeout=10)
            resp.raise_for_status()

            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0
            
            with open(final_file, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            dl_mb = downloaded / (1024 * 1024)
                            tot_mb = total_size / (1024 * 1024)
                            self.download_progress.emit(pct, dl_mb, tot_mb)

            self.log_entry.emit("OK", "DL", f"Download complete → {final_file}")
            self.status_changed.emit("status.loading_model", "OK")
            self.download_state_changed.emit(False)
            self.download_finished.emit(str(final_file))

        except Exception as e:
            import logging
            logging.getLogger("Katib").exception("Model downloader encountered an error:")

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
                self.log_entry.emit("ERR", "DL", f"Detailed Error: {err_msg}")

            self.log_entry.emit("ERR", "DL", user_msg)
            self.error_occurred.emit(osd_key)
            self.status_changed.emit("status.download_error", "ERR")
            self.download_state_changed.emit(False)
