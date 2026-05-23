"""
ModelDownloaderWorker testleri.
huggingface_hub.snapshot_download mock'lanır; internet bağlantısı gerekmez.
Atomik rename ve rollback davranışları gerçek geçici dizinlerle test edilir.
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
    """snapshot_download yerine: temp klasörü oluşturur, sahte model dosyası bırakır."""
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    (Path(local_dir) / "config.json").write_text("{}")


@pytest.fixture(autouse=True)
def mock_disk_space():
    """Diğer testlerin yetersiz disk alanından dolayı başarısız olmaması için 10 GB boş alan taklidi yapar."""
    mock_usage = MagicMock()
    mock_usage.free = 10 * 1024**3  # 10 GB
    with patch("workers.model_downloader_worker.shutil.disk_usage", return_value=mock_usage):
        yield


# ──────────────────────────────────────────── başlangıç durumu ──────────────

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
        # Herhangi bir hata veya çöküş fırlatmamalıdır
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


# ──────────────────────────────────────────── başarılı indirme ──────────────

class TestRunSuccess:
    """snapshot_download mock'lanır; run() doğrudan çağrılır (thread başlatılmaz)."""

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

    # --- sinyal sırası ---
    def test_download_state_sequence_true_then_false(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        assert s["state"] == [True, False]

    def test_emits_status_downloading_with_info(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        downloading = [(t, c) for t, c in s["status"] if "İndiriliyor" in t]
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

    # --- download_finished ---
    def test_download_finished_emitted_once(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        assert len(s["finished"]) == 1

    def test_download_finished_path_is_final_dir(self, qapp, tmp_path, mock_settings):
        _, s = self._run(tmp_path, mock_settings)
        assert s["finished"][0] == str(tmp_path / FINAL_MODEL_DIR_NAME)

    # --- dosya sistemi ---
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

    # --- snapshot_download çağrı parametreleri ---
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


# ───────────────────────────────────── rollback (hata durumu) ───────────────

class TestRunFailure:
    def _run_with_error(self, tmp_path, mock_settings, exc=None):
        if exc is None:
            exc = Exception("bağlantı kesildi")
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

    # --- sinyal doğruluğu ---
    def test_emits_error_occurred(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings)
        assert len(s["errors"]) == 1

    def test_error_message_is_user_friendly(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings, exc=Exception("MaxRetryError: Connection failed"))
        assert "İnternet bağlantısı koptu" in s["errors"][0]

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
        error_statuses = [(t, c) for t, c in s["status"] if "Hata" in t]
        assert error_statuses
        assert error_statuses[0][1] == "ERR"

    # --- rollback: temp dizin oluşturulmuşsa silinmeli ---
    def test_rollback_deletes_temp_dir(self, qapp, tmp_path, mock_settings):
        def partial_download(repo_id, local_dir, **_):
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            (Path(local_dir) / "partial.bin").write_text("yarım")
            raise Exception("koptu")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=partial_download):
            worker.run()

        assert not (tmp_path / f".temp_{FINAL_MODEL_DIR_NAME}").exists()

    def test_rollback_logs_cleanup_message(self, qapp, tmp_path, mock_settings):
        def partial_download(repo_id, local_dir, **_):
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            raise Exception("koptu")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))

        with patch("huggingface_hub.snapshot_download", side_effect=partial_download):
            worker.run()

        assert any("temizlendi" in m or "rollback" in m.lower() for m in logs)

    def test_rollback_when_temp_missing_does_not_crash(self, qapp, tmp_path, mock_settings):
        """snapshot_download temp dir oluşturmadan çöküyorsa rollback güvenli olmalı."""
        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=Exception("erken hata")):
            worker.run()   # temp_dir yok — shutil.rmtree çağrılmamalı, istisna olmamalı

    def test_final_dir_not_created_after_failure(self, qapp, tmp_path, mock_settings):
        self._run_with_error(tmp_path, mock_settings)
        assert not (tmp_path / FINAL_MODEL_DIR_NAME).exists()

    # --- çeşitli exception türleri ---
    def test_connection_error_handled(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings, exc=ConnectionError("no network"))
        assert len(s["errors"]) == 1

    def test_os_error_handled(self, qapp, tmp_path, mock_settings):
        s = self._run_with_error(tmp_path, mock_settings, exc=OSError("disk dolu"))
        assert len(s["errors"]) == 1

    def test_rollback_rmtree_failure_does_not_crash(self, qapp, tmp_path, mock_settings):
        """Rollback sırasında shutil.rmtree çökerse uygulama çökmemeli."""
        def partial_download(repo_id, local_dir, **_):
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            raise Exception("koptu")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        errors = []
        worker.error_occurred.connect(errors.append)

        with patch("huggingface_hub.snapshot_download", side_effect=partial_download):
            with patch("workers.model_downloader_worker.shutil.rmtree",
                       side_effect=PermissionError("kilitli")):
                worker.run()

        assert len(errors) == 1

    def test_rollback_rmtree_failure_emits_warning_log(self, qapp, tmp_path, mock_settings):
        """rmtree başarısız olursa sessizce yutulmamalı; WRN log düşmeli."""
        def partial_download(repo_id, local_dir, **_):
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            raise Exception("koptu")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, m)))

        with patch("huggingface_hub.snapshot_download", side_effect=partial_download):
            with patch("workers.model_downloader_worker.shutil.rmtree",
                       side_effect=PermissionError("kilitli")):
                worker.run()

        assert any(lvl == "WRN" and "silinemedi" in m for lvl, m in logs)


# ──────────────────────────────── mevcut model değiştirme (replace) ─────────

class TestRunExistingFinalDir:
    def test_existing_model_replaced_with_new(self, qapp, tmp_path, mock_settings):
        """Final dizin varsa, yeni model atomik olarak onun yerini almalı."""
        final_dir = tmp_path / FINAL_MODEL_DIR_NAME
        final_dir.mkdir()
        (final_dir / "old_config.json").write_text("{}")

        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = MODEL_REPO_ID
        with patch("huggingface_hub.snapshot_download", side_effect=_fake_download):
            worker.run()

        assert (final_dir / "config.json").exists()         # yeni dosya
        assert not (final_dir / "old_config.json").exists() # eski dosya gitti

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
        """Önceki çalışmadan kalan backup dizini varsa önce silinmeli."""
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


# ──────────────────────────────── mevcut temp dizini temizleme ───────────────

class TestPreexistingTempDir:
    def test_stale_temp_removed_before_download_call(self, qapp, tmp_path, mock_settings):
        """snapshot_download çağrıldığında eski temp'in dosyaları bulunmamalı."""
        temp_dir = tmp_path / f".temp_{FINAL_MODEL_DIR_NAME}"
        temp_dir.mkdir()
        (temp_dir / "stale_file.bin").write_text("eski veri")

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

        assert any("temizleniyor" in m.lower() for m in logs)

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


# ──────────────────────────────────────────── sabitler ──────────────────────

class TestConstants:
    def test_model_repo_id_is_systran_small(self, mock_settings):
        assert MODEL_REPO_ID == "Systran/faster-whisper-small"

    def test_final_model_dir_name_nonempty(self, mock_settings):
        assert FINAL_MODEL_DIR_NAME

    def test_default_download_parent_is_absolute(self, mock_settings):
        assert DEFAULT_DOWNLOAD_PARENT.is_absolute()

    def test_default_download_parent_under_home(self, mock_settings):
        assert DEFAULT_DOWNLOAD_PARENT.is_relative_to(Path.home())


# ───────────────────────────────────────── uçuş öncesi disk kontrolü ───────

class TestPreFlightDiskCheck:
    def test_insufficient_space_aborts_early(self, qapp, tmp_path, mock_settings):
        worker = ModelDownloaderWorker(mock_settings)
        worker._target_parent = tmp_path
        worker._repo_id = "Systran/faster-whisper-small" # 1 GB gerektirir

        mock_usage = MagicMock()
        mock_usage.free = 500 * 1024**2  # Sadece 500 MB boş

        errors = []
        worker.error_occurred.connect(errors.append)

        with patch("workers.model_downloader_worker.shutil.disk_usage", return_value=mock_usage), \
             patch("huggingface_hub.snapshot_download") as mock_download:
            worker.run()

        # İndirme fonksiyonu asla çağrılmamalı ve disk hatası fırlatılmalı
        assert len(errors) == 1
        assert "yeterli yer yok" in errors[0].lower()
        mock_download.assert_not_called()

    @pytest.mark.parametrize("repo_id, free_space, should_pass", [
        ("Systran/faster-whisper-large-v3", 3 * 1024**3, False),   # 4GB gerekir, 3GB var (HATA)
        ("Systran/faster-whisper-large-v3", 5 * 1024**3, True),    # 4GB gerekir, 5GB var (BAŞARILI)
        ("Systran/faster-whisper-medium", 1 * 1024**3, False),     # 2GB gerekir, 1GB var (HATA)
        ("Systran/faster-whisper-medium", 3 * 1024**3, True),      # 2GB gerekir, 3GB var (BAŞARILI)
        ("Systran/faster-whisper-tiny", 200 * 1024**2, False),     # 500MB gerekir, 200MB var (HATA)
        ("Systran/faster-whisper-tiny", 600 * 1024**2, True),      # 500MB gerekir, 600MB var (BAŞARILI)
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
            assert "yeterli yer yok" in errors[0].lower()


# ───────────────────────────────────────── hata mesajı eşleştirmeleri ──────

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

    @pytest.mark.parametrize("exc_text, expected_ui_text", [
        ("No space left on device", "yeterli boş alan yok"),
        ("404 Client Error: Repository Not Found", "Model bulunamadı"),
        ("MaxRetryError: Connection failed", "İnternet bağlantısı koptu"),
        ("Bilinmeyen rastgele bir hata", "İndirme başarısız"),
    ])
    def test_exception_message_translations(self, qapp, tmp_path, exc_text, expected_ui_text, mock_settings):
        msg = self._run_with_exception(tmp_path, mock_settings, exc_text)
        assert expected_ui_text in msg
