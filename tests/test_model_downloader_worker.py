"""
ModelDownloaderWorker tests.
huggingface_hub.snapshot_download is mocked; no internet connection required.
Atomic rename and rollback behaviour is tested with real temporary directories.
"""
from pathlib import Path
from unittest.mock import patch
import pytest
from workers.model_downloader_worker import (
    ModelDownloaderWorker,
    DEFAULT_DOWNLOAD_PARENT,
)

MODEL_REPO_ID = "Systran/faster-whisper-small"
FINAL_MODEL_DIR_NAME = "faster-whisper-small"

import sys
from unittest.mock import MagicMock
sys.modules['huggingface_hub'] = MagicMock()


def _fake_download(repo_id, local_dir, **_):
    """Replacement for snapshot_download: creates the temp folder and leaves a fake model file."""
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    (Path(local_dir) / "config.json").write_text("{}")


@pytest.fixture(autouse=True)
def mock_disk_space():
    """Simulates 10 GB of free disk space so other tests do not fail due to insufficient space."""
    mock_usage = MagicMock()
    mock_usage.free = 10 * 1024**3  # 10 GB
    with patch("workers.model_downloader_worker.shutil.disk_usage", return_value=mock_usage):
        yield


# ──────────────────────────────────────────── initial state ──────────────────

class TestInitialState:
    def test_target_parent_is_default(self, qapp, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        assert worker._target_parent == DEFAULT_DOWNLOAD_PARENT

    def test_required_signals_exist(self, qapp, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        for attr in ("log_entry", "error_occurred", "download_finished",
                     "status_changed", "download_state_changed"):
            assert hasattr(worker, attr)

    def test_not_running_on_creation(self, qapp, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        assert not worker.isRunning()

class TestStop:
    def test_stop_does_nothing(self, qapp, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        # Must not raise any error or crash
        worker.stop()


# ──────────────────────────────────────────── start_download ────────────────

class TestStartDownload:
    def test_sets_target_parent(self, qapp, tmp_path, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        with patch.object(worker, "start"):
            worker.start_download(str(tmp_path), MODEL_REPO_ID)
        assert worker._target_parent == tmp_path

    def test_target_parent_converted_to_path(self, qapp, tmp_path, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        with patch.object(worker, "start"):
            worker.start_download(str(tmp_path), MODEL_REPO_ID)
        assert isinstance(worker._target_parent, Path)

    def test_calls_qthread_start(self, qapp, tmp_path, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        with patch.object(worker, "start") as mock_start:
            worker.start_download(str(tmp_path), MODEL_REPO_ID)
        mock_start.assert_called_once()

    def test_double_call_while_running_emits_warning(self, qapp, tmp_path, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, m)))
        with patch.object(worker, "isRunning", return_value=True):
            worker.start_download(str(tmp_path), MODEL_REPO_ID)
        assert any(lvl == "WRN" for lvl, _ in logs)

    def test_double_call_while_running_does_not_restart(self, qapp, tmp_path, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        with patch.object(worker, "isRunning", return_value=True):
            with patch.object(worker, "start") as mock_start:
                worker.start_download(str(tmp_path), MODEL_REPO_ID)
        mock_start.assert_not_called()


# ──────────────────────────────────────────── successful download ────────────

class TestRunSuccess:
    """snapshot_download is mocked; run() is called directly (no thread is started)."""

    def _run(self, tmp_path, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID

        signals = {"state": [], "status": [], "logs": [], "finished": [], "errors": []}
        worker.download_state_changed.connect(signals["state"].append)
        worker.status_changed.connect(lambda t, c: signals["status"].append((t, c)))
        worker.log_entry.connect(lambda l, c, m: signals["logs"].append((l, c, m)))
        worker.download_finished.connect(signals["finished"].append)
        worker.error_occurred.connect(signals["errors"].append)

        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        return worker, signals

    # --- signal order ---
    def test_download_state_sequence_true_then_false(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        assert s["state"] == [True, False]

    def test_emits_status_downloading_with_info(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        downloading = [(t, c) for t, c in s["status"] if "status.downloading_model" in t]
        assert downloading
        assert downloading[0][1] == "INFO"

    def test_emits_ok_log(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        assert any(lvl == "OK" for lvl, _, _ in s["logs"])

    def test_log_contains_repo_id(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        assert any(MODEL_REPO_ID in m for _, _, m in s["logs"])

    def test_no_error_signals(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        assert s["errors"] == []

    # --- download_finished signal ---
    def test_download_finished_emitted_once(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        assert len(s["finished"]) == 1

    def test_download_finished_path_is_final_dir(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        assert s["finished"][0] == str(tmp_path / FINAL_MODEL_DIR_NAME)

    # --- filesystem ---
    def test_final_dir_exists(self, qapp, tmp_path, mock_settings):
        self._run(tmp_path, mock_settings)
        assert (tmp_path / FINAL_MODEL_DIR_NAME).is_dir()

    def test_temp_dir_absent_after_success(self, qapp, tmp_path, mock_settings):
        self._run(tmp_path, mock_settings)
        assert not (tmp_path / f".temp_{FINAL_MODEL_DIR_NAME}").exists()

    def test_model_files_preserved_in_final_dir(self, qapp, tmp_path, mock_settings):
        self._run(tmp_path, mock_settings)
        assert (tmp_path / FINAL_MODEL_DIR_NAME / "config.json").exists()

    def test_creates_target_parent_if_missing(self, qapp, tmp_path, mock_settings):
        deep = tmp_path / "a" / "b" / "c"
        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = deep
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()
        assert deep.is_dir()

    # --- snapshot_download call parameters ---
    def test_snapshot_download_receives_temp_dir_path(self, qapp, tmp_path, mock_settings):
        captured = []
        def capturing(repo_id, local_dir, **_):
            captured.append(local_dir)
            _fake_download(repo_id, local_dir)

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=capturing):
            worker.run()

        assert captured[0] == str(tmp_path / f".temp_{FINAL_MODEL_DIR_NAME}")

    def test_snapshot_download_repo_id_correct(self, qapp, tmp_path, mock_settings):
        captured = []
        def capturing(repo_id, local_dir, **_):
            captured.append(repo_id)
            _fake_download(repo_id, local_dir)

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=capturing):
            worker.run()

        assert captured[0] == MODEL_REPO_ID


# ───────────────────────────────────── rollback (error case) ────────────────

class TestRunFailure:
    def _run_with_error(self, tmp_path, mock_settings, exc=None):
        if exc is None:
            exc = Exception("connection dropped")
        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID

        signals = {"state": [], "errors": [], "finished": [], "logs": [], "status": []}
        worker.download_state_changed.connect(signals["state"].append)
        worker.error_occurred.connect(signals["errors"].append)
        worker.download_finished.connect(signals["finished"].append)
        worker.log_entry.connect(lambda l, c, m: signals["logs"].append((l, c, m)))
        worker.status_changed.connect(lambda t, c: signals["status"].append((t, c)))

        with patch("huggingface_hub.snapshot_download", side_effect=exc):
            worker.run()

        return signals

    # --- signal correctness ---
    def test_emits_error_occurred(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings)
        assert len(s["errors"]) == 1

    def test_error_message_is_user_friendly(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings, exc=Exception("MaxRetryError: Connection failed"))
        assert "osd.dl_no_internet" in s["errors"][0]

    def test_download_finished_not_emitted(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings)
        assert s["finished"] == []

    def test_download_state_sequence_true_then_false(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings)
        assert s["state"] == [True, False]

    def test_emits_err_log(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings)
        assert any(lvl == "ERR" for lvl, _, _ in s["logs"])

    def test_emits_status_error_level(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings)
        error_statuses = [(t, c) for t, c in s["status"] if "status.download_error" in t]
        assert error_statuses
        assert error_statuses[0][1] == "ERR"

    # --- rollback: temp directory must be deleted if it was created ---
    def test_rollback_deletes_temp_dir(self, qapp, tmp_path, mock_settings):
        def partial_download(repo_id, local_dir, **_):
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            (Path(local_dir) / "partial.bin").write_text("partial")
            raise Exception("dropped")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=partial_download):
            worker.run()

        assert not (tmp_path / f".temp_{FINAL_MODEL_DIR_NAME}").exists()

    def test_rollback_logs_cleanup_message(self, qapp, tmp_path, mock_settings):
        def partial_download(repo_id, local_dir, **_):
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            raise Exception("dropped")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))

        with patch("huggingface_hub.snapshot_download", side_effect=partial_download):
            worker.run()

        assert any("Rollback" in m or "rollback" in m.lower() for m in logs)

    def test_rollback_when_temp_missing_does_not_crash(self, qapp, tmp_path, mock_settings):
        """Rollback must be safe when snapshot_download crashes before creating the temp dir."""
        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=Exception("early error")):
            worker.run()   # temp_dir does not exist — shutil.rmtree must not be called, no exception

    def test_final_dir_not_created_after_failure(self, qapp, tmp_path, mock_settings):
        self._run_with_error(tmp_path, mock_settings)
        assert not (tmp_path / FINAL_MODEL_DIR_NAME).exists()

    # --- various exception types ---
    def test_connection_error_handled(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings, exc=ConnectionError("no network"))
        assert len(s["errors"]) == 1

    def test_os_error_handled(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings, exc=OSError("disk full"))
        assert len(s["errors"]) == 1

    def test_rollback_rmtree_failure_does_not_crash(self, qapp, tmp_path, mock_settings):
        """The app must not crash when shutil.rmtree fails during rollback."""
        def partial_download(repo_id, local_dir, **_):
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            raise Exception("dropped")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        errors = []
        worker.error_occurred.connect(errors.append)

        with patch("huggingface_hub.snapshot_download", side_effect=partial_download):
            with patch("workers.model_downloader_worker.shutil.rmtree",
                       side_effect=PermissionError("locked")):
                worker.run()

        assert len(errors) == 1

    def test_rollback_rmtree_failure_emits_warning_log(self, qapp, tmp_path, mock_settings):
        """A failed rmtree must not be swallowed silently; a WRN log must be emitted."""
        def partial_download(repo_id, local_dir, **_):
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            raise Exception("dropped")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, m)))

        with patch("huggingface_hub.snapshot_download", side_effect=partial_download):
            with patch("workers.model_downloader_worker.shutil.rmtree",
                       side_effect=PermissionError("locked")):
                worker.run()

        assert any(lvl == "WRN" and "Temporary files could not be deleted" in m for lvl, m in logs)


# ──────────────────────────────── replacing an existing model ───────────────

class TestRunExistingFinalDir:
    def test_existing_model_replaced_with_new(self, qapp, tmp_path, mock_settings):
        """If the final directory already exists, the new model must atomically replace it."""
        final_dir = tmp_path / FINAL_MODEL_DIR_NAME
        final_dir.mkdir()
        (final_dir / "old_config.json").write_text("{}")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        assert (final_dir / "config.json").exists()         # new file
        assert not (final_dir / "old_config.json").exists() # old file is gone

    def test_old_backup_cleaned_up_after_replace(self, qapp, tmp_path, mock_settings):
        final_dir = tmp_path / FINAL_MODEL_DIR_NAME
        final_dir.mkdir()

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        assert not (tmp_path / f".old_{FINAL_MODEL_DIR_NAME}").exists()

    def test_preexisting_stale_backup_cleared(self, qapp, tmp_path, mock_settings):
        """If a backup directory left over from a previous run exists, it must be deleted first."""
        final_dir = tmp_path / FINAL_MODEL_DIR_NAME
        final_dir.mkdir()
        stale = tmp_path / f".old_{FINAL_MODEL_DIR_NAME}"
        stale.mkdir()
        (stale / "stale.json").write_text("{}")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        assert not stale.exists()

    def test_download_finished_emitted_with_correct_path(self, qapp, tmp_path, mock_settings):
        final_dir = tmp_path / FINAL_MODEL_DIR_NAME
        final_dir.mkdir()

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        finished = []
        worker.download_finished.connect(finished.append)

        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        assert finished == [str(final_dir)]

    def test_no_error_signal_when_replacing(self, qapp, tmp_path, mock_settings):
        final_dir = tmp_path / FINAL_MODEL_DIR_NAME
        final_dir.mkdir()

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        errors = []
        worker.error_occurred.connect(errors.append)

        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        assert errors == []


# ──────────────────────────────── cleaning up an existing temp directory ─────

class TestPreexistingTempDir:
    def test_stale_temp_removed_before_download_call(self, qapp, tmp_path, mock_settings):
        """When snapshot_download is called, files from the old temp directory must not be present."""
        temp_dir = tmp_path / f".temp_{FINAL_MODEL_DIR_NAME}"
        temp_dir.mkdir()
        (temp_dir / "stale_file.bin").write_text("stale data")

        captured = {}
        def capturing(repo_id, local_dir, **_):
            captured["stale_exists"] = (Path(local_dir) / "stale_file.bin").exists()
            _fake_download(repo_id, local_dir)

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=capturing):
            worker.run()

        assert captured["stale_exists"] is False

    def test_stale_temp_cleanup_is_logged(self, qapp, tmp_path, mock_settings):
        temp_dir = tmp_path / f".temp_{FINAL_MODEL_DIR_NAME}"
        temp_dir.mkdir()

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))

        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        assert any("cleaning up" in m.lower() for m in logs)

    def test_success_still_completes_after_stale_cleanup(self, qapp, tmp_path, mock_settings):
        temp_dir = tmp_path / f".temp_{FINAL_MODEL_DIR_NAME}"
        temp_dir.mkdir()

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        finished = []
        worker.download_finished.connect(finished.append)

        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        assert len(finished) == 1


# ──────────────────────────────────────────── constants ─────────────────────

class TestConstants:
    def test_model_repo_id_is_systran_small(self, mock_settings):
        assert MODEL_REPO_ID == "Systran/faster-whisper-small"

    def test_final_model_dir_name_nonempty(self, mock_settings):
        assert FINAL_MODEL_DIR_NAME

    def test_default_download_parent_is_absolute(self, mock_settings):
        assert DEFAULT_DOWNLOAD_PARENT.is_absolute()

    def test_default_download_parent_under_home(self, mock_settings):
        assert DEFAULT_DOWNLOAD_PARENT.is_relative_to(Path.home())


# ───────────────────────────────────────── pre-flight disk check ────────────

class TestPreFlightDiskCheck:
    def test_insufficient_space_aborts_early(self, qapp, tmp_path, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = "Systran/faster-whisper-small" # requires 1 GB

        mock_usage = MagicMock()
        mock_usage.free = 500 * 1024**2  # only 500 MB free

        errors = []
        worker.error_occurred.connect(errors.append)

        with patch("workers.model_downloader_worker.shutil.disk_usage", return_value=mock_usage), \
             patch("huggingface_hub.snapshot_download") as mock_download:
            worker.run()

        # The download function must never be called and a disk error must be emitted
        assert len(errors) == 1
        assert "osd.dl_no_space" in errors[0]
        mock_download.assert_not_called()

    @pytest.mark.parametrize("repo_id, free_space, should_pass", [
        ("Systran/faster-whisper-large-v3", 3 * 1024**3, False),   # requires 4GB, 3GB available (FAIL)
        ("Systran/faster-whisper-large-v3", 5 * 1024**3, True),    # requires 4GB, 5GB available (PASS)
        ("Systran/faster-whisper-medium", 1 * 1024**3, False),     # requires 2GB, 1GB available (FAIL)
        ("Systran/faster-whisper-medium", 3 * 1024**3, True),      # requires 2GB, 3GB available (PASS)
        ("Systran/faster-whisper-tiny", 200 * 1024**2, False),     # requires 500MB, 200MB available (FAIL)
        ("Systran/faster-whisper-tiny", 600 * 1024**2, True),      # requires 500MB, 600MB available (PASS)
    ])
    def test_space_requirements_per_model_size(self, qapp, tmp_path, repo_id, free_space, should_pass, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = repo_id

        mock_usage = MagicMock()
        mock_usage.free = free_space

        errors = []
        worker.error_occurred.connect(errors.append)

        with patch("workers.model_downloader_worker.shutil.disk_usage", return_value=mock_usage), \
             patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        if should_pass:
            assert len(errors) == 0
        else:
            assert len(errors) == 1
            assert "osd.dl_no_space" in errors[0]


# ───────────────────────────────────────── exception message mappings ───────

class TestExceptionMessageMapping:
    def _run_with_exception(self, tmp_path, mock_settings, exc_message):
        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        errors = []
        worker.error_occurred.connect(errors.append)

        with patch("huggingface_hub.snapshot_download", side_effect=Exception(exc_message)):
            worker.run()
        return errors[0] if errors else None

    @pytest.mark.parametrize("exc_text, expected_osd_key", [
        ("No space left on device", "osd.dl_no_space"),
        ("404 Client Error: Repository Not Found", "osd.dl_model_not_found"),
        ("MaxRetryError: Connection failed", "osd.dl_no_internet"),
        ("Unknown random error", "osd.dl_failed"),
    ])
    def test_exception_message_translations(self, qapp, tmp_path, exc_text, expected_osd_key, mock_settings):
        msg = self._run_with_exception(tmp_path, mock_settings, exc_text)
        assert expected_osd_key in msg
