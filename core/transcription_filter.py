import re
import math
import unicodedata

# Stock phrases the models produce when handed silence.
HALLUCINATIONS = {
    "altyazi mk", "altyazi m k", "altyazi", "altyazilar",
    "abone olmayi unutmayin", "izlediginiz icin tesekkurler",
    "izlediginiz icin tesekkur ederim", "izlediginiz icin tesekkur ederiz",
    "kanalima abone olmayi unutmayin", "altyazi mk altyazi mk",
    "thanks for watching", "thank you for watching", "thanks for watching!",
    "please subscribe", "subscribe to my channel", "you", "bye",
    "mbc masr", "sous titres realises par la communaute damara org",
    "amara org community", "sous titrage st 501", "sessiz", "sessizlik", 
    "ceviri", "cevirmen", "muzik", "alkis", "tesekkurler", "izlediginiz icin"
}
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")

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

def _normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    return _SPACES.sub(" ", _PUNCTUATION.sub("", folded)).strip()

def looks_like_hallucination(text: str, duration_seconds: float, max_duration: float = 6.0) -> bool:
    """A stock phrase returned for a short clip is almost certainly invented."""
    if duration_seconds > max_duration:
        return False
    normalised = _normalise(text)
    if not normalised:
        return True
    if normalised in HALLUCINATIONS:
        return True
    # "Altyazı M.K. Altyazı M.K. Altyazı M.K.": the same stock line repeated.
    words = normalised.split()
    for phrase in HALLUCINATIONS:
        parts = phrase.split()
        if len(parts) >= 2 and words and len(words) % len(parts) == 0:
            if " ".join(words) == " ".join(parts * (len(words) // len(parts))):
                return True
    return False


class TranscriptionFilter:
    """Deep module that strips Whisper hallucinations and normalises text."""

    def clean(self, text: str, duration: float = 0.0) -> str | None:
        if not text:
            return None

        original_text = text.strip()
        
        # Check against hallucination rules
        if looks_like_hallucination(original_text, duration):
            return None
            
        # Run original Katib filter for backward compatibility
        norm_text = _normalise(original_text)
        
        # Original Katib logic: if ANY of these standalone words appear, drop it
        # We check exact match or if it's contained (which Katib did originally)
        katib_legacy_halls = ["sessiz", "sessizlik", "altyazi", "ceviri", "muzik", "alkis", "izlediginiz icin", "tesekkurler"]
        for h in katib_legacy_halls:
            if h in norm_text:
                return None
        
        return original_text
