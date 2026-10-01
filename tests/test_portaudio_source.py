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
