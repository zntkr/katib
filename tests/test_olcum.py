"""
scripts/olcum.py (plan 0007 Faz 1a): runs the user's own recordings through the
app's real decision chain. Whisper is faked; no model needed.
"""
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock
import numpy as np
import pytest

from scripts.olcum import Ayarlar, degerlendir, kelime_hata_orani, olc, rapor, wav_oku

SR = 16000


def _speech(seconds=2.0):
    """0.5 s of near-silence, then a loud tone: passes the app's level checks."""
    quiet = np.full(int(SR * 0.5), 1e-4, dtype=np.float32)
    t = np.arange(int(SR * (seconds - 0.5))) / SR
    return np.concatenate([quiet, (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)])


def _short_speech(seconds=0.4):
    t = np.arange(int(SR * seconds)) / SR
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def _model(text):
    model = MagicMock()
    model.transcribe.return_value = ([SimpleNamespace(text=text)] if text else [], MagicMock())
    return model


class TestKelimeHataOrani:
    @pytest.mark.parametrize("beklenen, cikan, oran", [
        ("bugün hava güzel", "bugün hava güzel", 0.0),
        ("bugün hava güzel", "bugün güzel", 1 / 3),
        ("bugün hava güzel", "", 1.0),
        ("İstanbul'a gittim.", "istanbul'a gittim", 0.0),   # case and punctuation do not count
        ("şu kitap", "su kitap", 0.5),                       # diacritics DO count
        ("", "", 0.0),
    ])
    def test_known_examples(self, beklenen, cikan, oran):
        assert kelime_hata_orani(beklenen, cikan) == pytest.approx(oran)


class TestDegerlendir:
    def test_too_short_recording_never_reaches_whisper(self):
        model = _model("Evet.")
        katman, _, _ = degerlendir(_short_speech(), model, Ayarlar())
        assert katman == "sure"
        model.transcribe.assert_not_called()

    def test_silent_recording_never_reaches_whisper(self):
        model = _model("Teşekkürler.")
        katman, _, _ = degerlendir(np.zeros(SR * 2, dtype=np.float32), model, Ayarlar())
        assert katman == "seviye"
        model.transcribe.assert_not_called()

    def test_speech_passes_with_the_apps_decoding_options(self):
        from workers.transcription_worker import TRANSCRIBE_OPTIONS
        model = _model(" Merhaba dünya.")
        katman, metin, ms = degerlendir(_speech(), model, Ayarlar(dil="tr"))
        assert (katman, metin) == (None, "Merhaba dünya.")
        assert ms is not None
        _, kwargs = model.transcribe.call_args
        assert kwargs["language"] == "tr"
        for key, value in TRANSCRIBE_OPTIONS.items():
            assert kwargs[key] == value

    def test_empty_whisper_output(self):
        assert degerlendir(_speech(), _model(""), Ayarlar())[0] == "whisper_bos"

    def test_hallucination_filter(self):
        assert degerlendir(_speech(), _model(" Altyazı M.K."), Ayarlar())[0] == "filtre"

    def test_settings_can_switch_layers_off(self):
        model = _model(" Evet.")
        katman, _, _ = degerlendir(_short_speech(), model, Ayarlar(min_sure=0.0, seviye=False, vad=False))
        assert katman is None
        assert model.transcribe.call_args[1]["vad_filter"] is False


class TestOlcVeRapor:
    def _wav(self, path, audio, rate=SR, channels=1):
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
        if channels == 2:
            pcm = np.repeat(pcm[:, None], 2, axis=1).reshape(-1)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm.tobytes())

    def test_wav_is_read_as_mono_16k(self, tmp_path):
        self._wav(tmp_path / "a.wav", np.zeros(48000, dtype=np.float32), rate=48000, channels=2)
        audio = wav_oku(tmp_path / "a.wav")
        assert audio.dtype == np.float32 and len(audio) == SR

    def test_counts_lost_speech_and_pasted_hallucinations(self, tmp_path):
        self._wav(tmp_path / "konusma.wav", _speech())
        (tmp_path / "konusma.txt").write_text("merhaba dünya", encoding="utf-8")
        self._wav(tmp_path / "bos.wav", _speech())
        (tmp_path / "bos.txt").write_text("", encoding="utf-8")   # no speech expected
        sonuclar = olc(tmp_path, _model(" Merhaba dünya."), Ayarlar())
        metin = rapor(sonuclar)
        assert "Konuşmalı kayıt: 1" in metin and "elenen: 0" in metin
        assert "Konuşmasız kayıt: 1" in metin and "yapıştırılırdı: 1" in metin

    def test_report_hides_dictated_text_by_default(self, tmp_path):
        self._wav(tmp_path / "k.wav", _speech())
        (tmp_path / "k.txt").write_text("gizli cümle", encoding="utf-8")
        sonuclar = olc(tmp_path, _model(" Gizli cümle."), Ayarlar())
        assert "Gizli" not in rapor(sonuclar)
        assert "Gizli" in rapor(sonuclar, metin_goster=True)
