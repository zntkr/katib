"""
PortAudioSource stream-lifecycle tests. sounddevice is mocked globally in conftest.py.
"""
from unittest.mock import MagicMock, call
import pytest

from core import portaudio_source
from core.portaudio_source import PortAudioSource
from core.audio_source import AudioDisconnectedError


@pytest.fixture
def source():
    return PortAudioSource()


class TestUnexpectedStreamEnd:
    def test_reports_disconnect(self, source):
        finished = MagicMock()
        source._finished_callback = finished
        source._stream = MagicMock()
        source._sd_finished_callback()
        err = finished.call_args[0][0]
        assert isinstance(err, AudioDisconnectedError)

    def test_does_not_close_stream_inside_callback(self, source):
        """Closing a stream from its own finished callback is forbidden by PortAudio."""
        stream = MagicMock()
        source._finished_callback = MagicMock()
        source._stream = stream
        source._sd_finished_callback()
        stream.close.assert_not_called()
        assert source._stream is None

    def test_dead_stream_closed_before_portaudio_reinit(self, source, monkeypatch):
        order = MagicMock()
        stream = order.stream
        sd = MagicMock()
        sd._terminate = order.terminate
        sd.query_devices.return_value = []
        sd.query_hostapis.return_value = []
        monkeypatch.setattr(portaudio_source, "sd", sd)

        source._finished_callback = MagicMock()
        source._stream = stream
        source._sd_finished_callback()
        source.refresh_devices()

        assert order.mock_calls.index(call.stream.close()) < order.mock_calls.index(call.terminate())

    def test_dead_stream_closed_on_stop(self, source):
        stream = MagicMock()
        source._finished_callback = MagicMock()
        source._stream = stream
        source._sd_finished_callback()
        source.stop()
        stream.close.assert_called_once()

    def test_intentional_close_reports_no_error(self, source):
        finished = MagicMock()
        source._finished_callback = finished
        source._stream = MagicMock()
        source._intentional_close = True
        source._sd_finished_callback()
        finished.assert_called_once_with(None)


class TestStop:
    """Plan 0002: stop() must close the stream even when PortAudio runs the
    finished callback inside stream.stop() (it sets self._stream = None)."""

    def test_stop_closes_stream_even_if_finished_callback_runs_inside_stop(self, source):
        stream = MagicMock()
        source._finished_callback = MagicMock()
        source._stream = stream
        stream.stop.side_effect = lambda: source._sd_finished_callback()
        source.stop()
        stream.close.assert_called_once()
        assert source._stream is None

    def test_stop_logs_close_errors(self, source):
        from tests.log_helpers import on_log_entry
        logs = []
        on_log_entry(lambda lvl, comp, msg: logs.append((lvl, comp, msg)))
        stream = MagicMock()
        stream.close.side_effect = RuntimeError("device busy")
        source._stream = stream
        source.stop()
        assert any(lvl == "WRN" and comp == "MIC" and "device busy" in msg for lvl, comp, msg in logs)


class TestOpenInOneAttempt:
    """Plan 0006 Faz 2: WASAPI rejects 16 kHz without conversion; the source must not
    pay a failed open on every key press."""

    @pytest.fixture
    def fake_sd(self, monkeypatch):
        sd = MagicMock()
        sd.query_devices.return_value = {"max_input_channels": 1, "default_samplerate": 48000, "name": "Mic"}
        opened = []

        def input_stream(samplerate, extra_settings=None, **kwargs):
            opened.append((samplerate, extra_settings))
            if samplerate == 16000 and extra_settings is None:
                raise portaudio_source._PortAudioError("Invalid sample rate [PaErrorCode -9997]")
            return MagicMock()

        sd.InputStream.side_effect = input_stream
        monkeypatch.setattr(portaudio_source, "sd", sd)
        return sd, opened

    def _press(self, source):
        source.start(MagicMock(), MagicMock())
        source.stop()

    def test_working_rate_is_remembered_after_a_rejected_16k(self, source, fake_sd, monkeypatch):
        monkeypatch.setattr(portaudio_source.sys, "platform", "linux")
        _, opened = fake_sd
        source.set_device(1)
        self._press(source)
        assert opened == [(16000, None), (48000, None)]
        opened.clear()
        self._press(source)
        assert opened == [(48000, None)]
        assert source.native_sample_rate == 48000

    def test_device_change_forgets_the_remembered_rate(self, source, fake_sd, monkeypatch):
        monkeypatch.setattr(portaudio_source.sys, "platform", "linux")
        _, opened = fake_sd
        source.set_device(1)
        self._press(source)
        source.set_device(2)
        opened.clear()
        self._press(source)
        assert opened[0] == (16000, None)

    def test_windows_asks_wasapi_to_convert_to_16k_first(self, source, fake_sd, monkeypatch):
        monkeypatch.setattr(portaudio_source.sys, "platform", "win32")
        sd, opened = fake_sd
        source.set_device(1)
        self._press(source)
        sd.WasapiSettings.assert_called_with(auto_convert=True)
        assert opened == [(16000, sd.WasapiSettings.return_value)]
        assert source.native_sample_rate == 16000

    def test_fallback_rate_is_logged(self, source, fake_sd, monkeypatch):
        from tests.log_helpers import on_log_entry
        monkeypatch.setattr(portaudio_source.sys, "platform", "linux")
        logs = []
        on_log_entry(lambda lvl, comp, msg: logs.append(msg))
        source.set_device(1)
        self._press(source)
        assert any("48000 Hz" in m for m in logs)

    def test_stream_that_fails_to_start_is_closed(self, source, fake_sd, monkeypatch):
        monkeypatch.setattr(portaudio_source.sys, "platform", "linux")
        sd, _ = fake_sd
        broken = MagicMock()
        broken.start.side_effect = RuntimeError("device busy")
        good = MagicMock()
        sd.InputStream.side_effect = [broken, good]
        source.set_device(1)
        source.start(MagicMock(), MagicMock())
        broken.close.assert_called_once()
        assert source._stream is good
