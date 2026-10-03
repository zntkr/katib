"""core.gpu: deciding whether the GPU can be used (plan 0009). No real GPU or CUDA library is needed."""
import os
import sys
from unittest.mock import MagicMock

import pytest

from core import gpu
from core.gpu import unavailable_reason  # the real one: conftest replaces the module attribute


def _make_dir(path, names):
    path.mkdir(parents=True, exist_ok=True)
    for name in names:
        (path / name).write_bytes(b"")
    return path


class TestLibraryDir:

    def test_finds_the_folder_holding_every_required_library(self, tmp_path):
        other = _make_dir(tmp_path / "cudnn" / "bin", ["cudnn64_9.dll"])
        cublas = _make_dir(tmp_path / "cublas" / "bin", gpu.REQUIRED_DLLS)
        assert gpu.library_dir([other, cublas]) == cublas

    def test_a_partial_install_does_not_count(self, tmp_path):
        partial = _make_dir(tmp_path / "bin", gpu.REQUIRED_DLLS[:1])
        assert gpu.library_dir([partial]) is None

    def test_missing_folders_are_skipped(self, tmp_path):
        assert gpu.library_dir([tmp_path / "nope"]) is None


class TestCandidateDirs:

    def test_pip_wheel_folders_are_candidates(self, tmp_path, monkeypatch):
        wheel = _make_dir(tmp_path / "nvidia" / "cublas" / "bin", [])
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.setattr("site.getsitepackages", lambda: [str(tmp_path)])
        monkeypatch.setattr("site.getusersitepackages", lambda: str(tmp_path / "user"))
        assert wheel in gpu.candidate_dirs()

    def test_a_frozen_build_looks_inside_its_own_bundle(self, tmp_path, monkeypatch):
        bundled = _make_dir(tmp_path / "bundle" / "nvidia" / "cublas" / "bin", [])
        wheel = _make_dir(tmp_path / "site" / "nvidia" / "cublas" / "bin", [])
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
        monkeypatch.setattr("site.getsitepackages", lambda: [str(tmp_path / "site")])
        candidates = gpu.candidate_dirs()
        assert bundled in candidates and wheel not in candidates

    def test_folders_on_path_are_candidates(self, tmp_path, monkeypatch):
        toolkit = _make_dir(tmp_path / "CUDA" / "bin", [])
        monkeypatch.setenv("PATH", str(toolkit) + os.pathsep + os.environ.get("PATH", ""))
        assert toolkit in gpu.candidate_dirs()


class TestUnavailableReason:

    @pytest.fixture
    def machine(self, tmp_path, monkeypatch):
        """A machine with one NVIDIA GPU and the libraries installed; tests break one thing each."""
        libs = _make_dir(tmp_path / "nvidia" / "cublas" / "bin", gpu.REQUIRED_DLLS)
        monkeypatch.setattr(gpu, "_cuda_device_count", lambda: 1)
        monkeypatch.setattr(gpu, "candidate_dirs", lambda: [libs])
        monkeypatch.setattr(os, "add_dll_directory", MagicMock(), raising=False)
        monkeypatch.setenv("PATH", r"C:\somewhere")
        return libs

    def test_usable_when_a_gpu_and_the_libraries_are_present(self, machine):
        assert unavailable_reason() is None

    def test_a_usable_gpu_gets_its_libraries_on_the_dll_search_path(self, machine):
        unavailable_reason()
        assert os.environ["PATH"].split(os.pathsep)[0] == str(machine)
        os.add_dll_directory.assert_called_with(str(machine))

    def test_the_search_path_is_not_extended_twice(self, machine):
        unavailable_reason()
        unavailable_reason()
        assert os.environ["PATH"].split(os.pathsep).count(str(machine)) == 1

    def test_no_nvidia_gpu(self, machine, monkeypatch):
        monkeypatch.setattr(gpu, "_cuda_device_count", lambda: 0)
        assert "no NVIDIA GPU" in unavailable_reason()

    def test_missing_libraries_are_named(self, machine, monkeypatch):
        monkeypatch.setattr(gpu, "candidate_dirs", lambda: [])
        reason = unavailable_reason()
        assert all(name in reason for name in gpu.REQUIRED_DLLS)

    def test_a_failing_gpu_query_is_a_reason_not_a_crash(self, machine, monkeypatch):
        def boom():
            raise RuntimeError("driver too old")
        monkeypatch.setattr(gpu, "_cuda_device_count", boom)
        assert "driver too old" in unavailable_reason()


class TestComputeType:

    def test_float16_when_the_card_supports_it(self, monkeypatch):
        monkeypatch.setattr(gpu, "_supported_compute_types", lambda: {"float16", "float32", "int8"})
        assert gpu.compute_type() == "float16"

    def test_older_cards_get_float32(self, monkeypatch):
        monkeypatch.setattr(gpu, "_supported_compute_types", lambda: {"float32", "int8"})
        assert gpu.compute_type() == "float32"
