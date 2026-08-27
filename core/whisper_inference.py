import os
import time
import subprocess
import requests
import io
import wave
import socket
import numpy as np

def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

class WhisperInferenceModule:
    def __init__(self):
        self._server_proc = None
        self._port = None

    def start_server(self, model_path: str, server_exe: str) -> None:
        self.stop_server()

        self._port = _find_free_port()
        cmd = [
            str(server_exe),
            "-m", str(model_path),
            "--port", str(self._port),
            "--host", "127.0.0.1"
        ]

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self._server_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo
        )

        server_ready = False
        for _ in range(30):
            try:
                resp = requests.get(f"http://127.0.0.1:{self._port}/", timeout=1)
                if resp.status_code == 200:
                    server_ready = True
                    break
            except Exception:
                pass
            time.sleep(0.5)

        if not server_ready:
            raise RuntimeError("Server failed to respond to HTTP requests.")

    def stop_server(self) -> None:
        if self._server_proc:
            try:
                self._server_proc.terminate()
                self._server_proc.wait(timeout=2)
            except Exception:
                pass
            self._server_proc = None
            self._port = None

    def transcribe(self, audio: np.ndarray, language: str) -> str:
        if not self._server_proc or self._server_proc.poll() is not None:
            raise RuntimeError("Server is not running.")

        # Convert float32 numpy array to 16-bit PCM WAV in memory
        audio_int16 = (audio * 32767).astype(np.int16)
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio_int16.tobytes())
        
        wav_data = wav_io.getvalue()

        files = {'file': ('audio.wav', wav_data, 'audio/wav')}
        data = {
            'response_format': 'json',
        }
        if language != "auto":
            data['language'] = language

        resp = requests.post(
            f"http://127.0.0.1:{self._port}/inference", 
            files=files, 
            data=data,
            timeout=30
        )
        resp.raise_for_status()

        result = resp.json()
        raw_text = result.get("text", "").strip()
        return raw_text
