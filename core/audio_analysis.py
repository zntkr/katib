import math

def to_db(value: float) -> float:
    return 20 * math.log10(value) if value > 0 else -120.0

def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, int(len(values) * fraction)))
    return values[index]

def analyse_vad(rms_values: list[float], chunk_seconds: float, margin_db: float = 10.0) -> dict:
    """Turn per-chunk RMS levels into the numbers the decision needs."""
    if not rms_values:
        return {"noise_db": -120.0, "speech_db": -120.0,
                "dynamic_db": 0.0, "voiced_seconds": 0.0}

    ordered = sorted(rms_values)
    noise = _percentile(ordered, 0.10)
    speech = _percentile(ordered, 0.90)
    noise_db, speech_db = to_db(noise), to_db(speech)

    # Anything this far above the recording's own floor counts as voice.
    gate_db = noise_db + margin_db
    voiced = sum(1 for value in rms_values if to_db(value) >= gate_db)

    return {
        "noise_db": noise_db,
        "speech_db": speech_db,
        "dynamic_db": speech_db - noise_db,
        "voiced_seconds": voiced * chunk_seconds,
    }

def is_silent(stats: dict, silence_db: float = -55.0, margin_db: float = 10.0, min_voiced_seconds: float = 0.3) -> bool:
    """True when the recording holds no speech worth sending to the API.

    Three independent reasons, any one of which is enough:
      * the loud end of the recording is below the absolute floor
      * nothing rose far enough above the noise floor for long enough
      * the level never moved, meaning steady hiss, hum or fan noise
    """
    if stats["speech_db"] < silence_db:
        return True
    if stats["voiced_seconds"] < min_voiced_seconds:
        return True
    # Only distrust flat dynamics near the floor; a loud, evenly-spoken
    # sentence legitimately has a narrow range.
    if stats["speech_db"] < silence_db + 12 and stats["dynamic_db"] < margin_db * 0.6:
        return True
    return False
