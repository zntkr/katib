import pytest
import math
from core.audio_analysis import to_db, analyse_vad, is_silent

def test_to_db():
    assert math.isclose(to_db(1.0), 0.0)
    assert math.isclose(to_db(0.1), -20.0)
    assert to_db(0.0) == -120.0
    assert to_db(-1.0) == -120.0

def test_analyse_vad_empty():
    res = analyse_vad([], 0.1)
    assert res["noise_db"] == -120.0
    assert res["speech_db"] == -120.0
    assert res["dynamic_db"] == 0.0
    assert res["voiced_seconds"] == 0.0

def test_analyse_vad_logic():
    # Provide values that span a range. 
    # to_db(0.01) = -40, to_db(0.1) = -20
    # Values: [0.01, 0.01, 0.01, 0.1, 0.1]
    res = analyse_vad([0.01, 0.01, 0.01, 0.1, 0.1], 0.1, margin_db=10.0)
    
    # 0.10 percentile -> index 0 -> 0.01 (-40 dB)
    assert math.isclose(res["noise_db"], -40.0)
    # 0.90 percentile -> index 4 -> 0.1 (-20 dB)
    assert math.isclose(res["speech_db"], -20.0)
    
    # dynamic_db = speech - noise = 20
    assert math.isclose(res["dynamic_db"], 20.0)
    
    # gate_db = noise + margin = -30
    # Values >= -30 dB are the two 0.1 values.
    # Voiced = 2
    assert math.isclose(res["voiced_seconds"], 0.2)

def test_is_silent_below_floor():
    stats = {"speech_db": -60.0, "voiced_seconds": 1.0, "dynamic_db": 20.0}
    assert is_silent(stats, silence_db=-55.0) is True

def test_is_silent_not_enough_voiced_time():
    stats = {"speech_db": -40.0, "voiced_seconds": 0.2, "dynamic_db": 20.0}
    assert is_silent(stats, min_voiced_seconds=0.3) is True

def test_is_silent_flat_dynamics():
    stats = {"speech_db": -50.0, "voiced_seconds": 1.0, "dynamic_db": 2.0}
    # speech_db (-50) < silence_db(-55) + 12 (-43)
    # dynamic_db (2) < margin_db(10) * 0.6 (6)
    assert is_silent(stats, silence_db=-55.0, margin_db=10.0) is True

def test_is_not_silent():
    stats = {"speech_db": -40.0, "voiced_seconds": 1.0, "dynamic_db": 15.0}
    assert is_silent(stats, silence_db=-55.0, min_voiced_seconds=0.3, margin_db=10.0) is False
