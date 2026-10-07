"""
scripts/olcum.py (plan 0007 Faz 1a): runs the user's own recordings through the
app's real decision chain. Whisper is faked; no model needed.
"""
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from scripts.olcum import (
    Ayarlar, Sonuc, cozumleme, degerlendir, kelime_hata_orani, main, model_ac, olc, rapor,
    sure_ozeti, wav_oku,
)
from workers.transcription_worker import TRANSCRIBE_OPTIONS

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


# ------------------------------------------------------------------ plan 0012 Faz 2

def _sonuc(sure_sn, ms):
    return Sonuc("a.wav", True, None, 0.0, ms, "", sure_sn)


class TestCozumleme:
    def test_without_overrides_it_is_the_apps_options(self):
        assert cozumleme(Ayarlar()) == dict(TRANSCRIBE_OPTIONS, vad_filter=True)

    def test_overrides_reach_the_options(self):
        options = cozumleme(Ayarlar(beam=1, zaman_damgasiz=True, sicaklik=(0.0,), vad=False))
        assert options["beam_size"] == 1
        assert options["without_timestamps"] is True
        assert options["temperature"] == 0.0
        assert options["vad_filter"] is False

    def test_a_temperature_list_stays_a_list(self):
        assert cozumleme(Ayarlar(sicaklik=(0.0, 0.4)))["temperature"] == [0.0, 0.4]

    def test_overrides_are_what_whisper_is_called_with(self):
        model = _model(" Merhaba.")
        degerlendir(_speech(), model, Ayarlar(beam=1, zaman_damgasiz=True))
        kwargs = model.transcribe.call_args[1]
        assert kwargs["beam_size"] == 1 and kwargs["without_timestamps"] is True


class TestTekrar:
    def test_each_recording_runs_n_times_and_reports_the_median(self):
        model = _model(" Merhaba.")
        # start/end pairs: 100 ms, 300 ms, 200 ms → median 200 ms
        clock = [0.0, 0.1, 1.0, 1.3, 2.0, 2.2]
        with patch("scripts.olcum.time.perf_counter", side_effect=clock):
            katman, _, ms = degerlendir(_speech(), model, Ayarlar(tekrar=3))
        assert katman is None
        assert model.transcribe.call_count == 3
        assert ms == pytest.approx(200.0)


class TestSureOzeti:
    def test_times_are_split_by_recording_length(self):
        sonuclar = [_sonuc(2.0, 100), _sonuc(3.0, 300), _sonuc(20.0, 1500), _sonuc(40.0, 4000)]
        satirlar = sure_ozeti(sonuclar)
        assert satirlar[0].startswith("Whisper süresi: medyan 900 ms")
        assert any("< 5 sn" in line and "medyan 200 ms" in line and "(2 kayıt)" in line for line in satirlar)
        assert any("15–30 sn" in line and "medyan 1500 ms" in line for line in satirlar)
        assert any("> 30 sn" in line and "medyan 4000 ms" in line for line in satirlar)
        assert not any("5–15 sn" in line for line in satirlar)  # empty bucket is left out

    def test_nothing_measured_gives_no_lines(self):
        assert sure_ozeti([Sonuc("a.wav", True, "sure", 1.0, None, "", 0.3)]) == []

    def test_report_shows_the_recording_length(self, tmp_path):
        TestOlcVeRapor()._wav(tmp_path / "k.wav", _speech(2.0))
        (tmp_path / "k.txt").write_text("merhaba", encoding="utf-8")
        metin = rapor(olc(tmp_path, _model(" Merhaba."), Ayarlar()))
        assert "  2.0 " in metin and "< 5 sn" in metin


class TestModelAc:
    @pytest.fixture
    def whisper(self):
        with patch("faster_whisper.WhisperModel") as cls:
            yield cls

    def test_auto_without_a_gpu_opens_on_the_cpu_with_the_users_precision(self, whisper):
        _, cihaz, compute_type = model_ac("m", "auto", None, 0, "int8")
        assert (cihaz, compute_type) == ("cpu", "int8")
        assert whisper.call_args[1]["device"] == "cpu"

    def test_auto_with_a_gpu_opens_on_the_gpu(self, whisper):
        with patch("core.gpu.unavailable_reason", return_value=None), \
             patch("core.gpu.compute_type", return_value="float16"):
            _, cihaz, compute_type = model_ac("m", "auto", None, 0, "int8")
        assert (cihaz, compute_type) == ("cuda", "float16")

    def test_cuda_without_a_gpu_stops_with_the_reason(self, whisper):
        with pytest.raises(SystemExit, match="disabled in tests"):
            model_ac("m", "cuda", None, 0, "int8")
        whisper.assert_not_called()

    def test_threads_and_precision_can_be_forced(self, whisper):
        model_ac("m", "cpu", "float32", 8, "int8")
        kwargs = whisper.call_args[1]
        assert (kwargs["compute_type"], kwargs["cpu_threads"]) == ("float32", 8)


class TestMain:
    def _run(self, tmp_path, *args, language="auto"):
        TestOlcVeRapor()._wav(tmp_path / "k.wav", _speech())
        (tmp_path / "k.txt").write_text("merhaba", encoding="utf-8")
        model = _model(" Merhaba.")
        settings = MagicMock()
        settings.get.side_effect = lambda key, default=None: {
            "language": language, "compute_type": "int8", "initial_prompt": ""}.get(key, default)
        order = MagicMock()
        with patch("core.settings.SettingsManager", return_value=settings), \
             patch("scripts.olcum.model_ac", return_value=(model, "cpu", "int8")), \
             patch("scripts.olcum.warm_up", side_effect=lambda *a: order.warm_up(*a)) as warm, \
             patch("scripts.olcum.olc", side_effect=lambda *a: order.olc() or []):
            assert main(["--klasor", str(tmp_path), "--model", "m", *args]) == 0
        return warm, order

    def test_the_model_is_warmed_up_before_anything_is_measured(self, tmp_path):
        _, order = self._run(tmp_path)
        assert [c[0] for c in order.mock_calls if c[0] in ("warm_up", "olc")] == ["warm_up", "olc"]

    def test_auto_language_setting_means_detection(self, tmp_path):
        warm, _ = self._run(tmp_path, language="auto")
        assert warm.call_args[0][1] is None

    def test_warm_up_uses_the_measured_options(self, tmp_path):
        warm, _ = self._run(tmp_path, "--dil", "tr", "--beam", "1")
        model, dil, options = warm.call_args[0]
        assert dil == "tr" and options["beam_size"] == 1


# ------------------------------------------------------------------ plan 0014 Faz 1: --parcali

from scripts.olcum import parcali_cozumle, parcali_olc, parcali_rapor  # noqa: E402


def _echo_model():
    """Whisper that 'transcribes' a piece as its length in whole seconds, and records prompts."""
    model = MagicMock()

    def transcribe(audio, **kwargs):
        return [SimpleNamespace(text=f" p{round(len(audio) / SR)}")], MagicMock()
    model.transcribe.side_effect = transcribe
    return model


def _cut_once_at(seconds):
    """A cutter that cuts at `seconds` into the first window long enough, then never again."""
    state = {"done": False}

    def kesici(audio):
        if state["done"] or len(audio) < seconds * SR + SR:
            return None
        state["done"] = True
        return int(seconds * SR)
    return kesici


class TestParcaliCozumle:
    def test_pieces_go_ahead_and_only_the_rest_is_left_for_release(self):
        audio = np.zeros(20 * SR, dtype=np.float32)
        metin, parca, kalan_ms, yetisme = parcali_cozumle(audio, _echo_model(), Ayarlar(), kesici=_cut_once_at(9))
        assert metin == "p9 p11"
        assert parca == 1
        assert yetisme >= 0

    def test_the_next_piece_is_prompted_with_the_text_so_far(self):
        model = _echo_model()
        audio = np.zeros(20 * SR, dtype=np.float32)
        parcali_cozumle(audio, model, Ayarlar(prompt="Katib"), kesici=_cut_once_at(9))
        prompts = [c.kwargs["initial_prompt"] for c in model.transcribe.call_args_list]
        assert prompts == ["Katib", "Katib p9"]

    def test_without_a_cut_it_is_one_decode_like_today(self):
        model = _echo_model()
        metin, parca, _, yetisme = parcali_cozumle(np.zeros(20 * SR, dtype=np.float32), model, Ayarlar(),
                                                   kesici=lambda a: None)
        assert (metin, parca, yetisme) == ("p20", 0, 0.0)
        assert model.transcribe.call_count == 1

    def test_the_cutter_sees_only_audio_not_yet_cut_off_and_received_so_far(self):
        seen = []
        def kesici(audio):
            seen.append(len(audio) / SR)
            return int(4 * SR) if len(seen) == 2 else None
        parcali_cozumle(np.zeros(13 * SR, dtype=np.float32), _echo_model(), Ayarlar(), kesici=kesici, adim_sn=3)
        assert seen == [3, 6, 5, 8]  # 3, 6 → cut 4 s off → 9-4, 12-4


class TestParcaliOlc:
    def _wav(self, path, seconds):
        TestOlcVeRapor()._wav(path, _speech(seconds))

    def test_compares_whole_and_piecewise_for_long_spoken_recordings(self, tmp_path):
        self._wav(tmp_path / "uzun.wav", 20.0)
        (tmp_path / "uzun.txt").write_text("p20", encoding="utf-8")
        self._wav(tmp_path / "kisa.wav", 4.0)
        (tmp_path / "kisa.txt").write_text("p4", encoding="utf-8")
        self._wav(tmp_path / "bos.wav", 20.0)
        (tmp_path / "bos.txt").write_text("", encoding="utf-8")
        sonuclar, kisa = parcali_olc(tmp_path, _echo_model(), Ayarlar(), kesici=_cut_once_at(9))
        assert kisa == 1 and [s.dosya for s in sonuclar] == ["uzun.wav"]
        s = sonuclar[0]
        assert (s.parca, s.wer_butun, s.metin_parcali) == (1, 0.0, "p9 p11")
        assert s.wer_parcali == 2.0  # "p9 p11" vs "p20": a substitution and an insertion over one word

    def test_report(self, tmp_path):
        self._wav(tmp_path / "uzun.wav", 20.0)
        (tmp_path / "uzun.txt").write_text("gizli metin", encoding="utf-8")
        sonuclar, kisa = parcali_olc(tmp_path, _echo_model(), Ayarlar(), kesici=_cut_once_at(9))
        metin = parcali_rapor(sonuclar, kisa)
        assert "en az bir parçası arka planda çözümlenen: 1" in metin
        assert "Bırakıştan sonra Whisper: bütün medyan" in metin
        assert "konuşmaya yetişiyor" in metin
        assert "p9 p11" not in metin and "p9 p11" in parcali_rapor(sonuclar, kisa, metin_goster=True)

    def test_report_without_long_recordings(self):
        assert "Parçalanacak uzunlukta konuşmalı kayıt yok" in parcali_rapor([], 2)


class TestMainParcali:
    def test_parcali_flag_runs_the_piecewise_comparison(self, tmp_path):
        with patch("scripts.olcum.parcali_olc", return_value=([], 0)) as parcali, \
             patch("scripts.olcum.olc") as butun:
            TestMain()._run(tmp_path, "--parcali")
        parcali.assert_called_once()
        butun.assert_not_called()
