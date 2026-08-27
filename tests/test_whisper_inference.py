import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from core.whisper_inference import WhisperInferenceModule
import requests

@pytest.fixture
def inference_module():
    return WhisperInferenceModule()

class TestStartServer:
    @patch("subprocess.Popen")
    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_starts_server_and_polls(self, mock_get, mock_sleep, mock_popen, inference_module):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        
        # Simulate server responding on 2nd attempt
        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 500
        mock_resp_success = MagicMock()
        mock_resp_success.status_code = 200
        mock_get.side_effect = [requests.exceptions.ConnectionError, mock_resp_fail, mock_resp_success]
        
        inference_module.start_server("/path/to/model", "whisper-server.exe")
        
        assert mock_popen.called
        assert mock_get.call_count == 3
        assert inference_module._server_proc == mock_proc
        assert inference_module._port is not None

    @patch("subprocess.Popen")
    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_raises_if_server_fails_to_start(self, mock_get, mock_sleep, mock_popen, inference_module):
        mock_get.side_effect = requests.exceptions.ConnectionError
        with pytest.raises(RuntimeError, match="Server failed to respond"):
            inference_module.start_server("/path/to/model", "whisper-server.exe")

class TestStopServer:
    def test_stops_running_server(self, inference_module):
        mock_proc = MagicMock()
        inference_module._server_proc = mock_proc
        inference_module.stop_server()
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=2)
        assert inference_module._server_proc is None

class TestTranscribe:
    @patch("requests.post")
    def test_transcribe_success(self, mock_post, inference_module):
        inference_module._port = 8080
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        inference_module._server_proc = mock_proc

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"text": "hello test"}
        mock_post.return_value = mock_resp

        audio = np.zeros(16000, dtype="float32")
        result = inference_module.transcribe(audio, "en")
        
        assert result == "hello test"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["data"]["language"] == "en"
        assert kwargs["data"]["response_format"] == "json"
        assert "file" in kwargs["files"]

    def test_transcribe_fails_if_server_not_running(self, inference_module):
        inference_module._server_proc = None
        with pytest.raises(RuntimeError, match="Server is not running"):
            audio = np.zeros(160, dtype="float32")
            inference_module.transcribe(audio, "auto")
