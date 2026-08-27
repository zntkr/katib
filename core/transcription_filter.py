import re

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
