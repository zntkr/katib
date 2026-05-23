import re

class TranscriptionFilter:
    """Deep module that strips Whisper hallucinations and normalises text."""

    def __init__(self):
        # Typical words Whisper fabricates when it hears only noise.
        self.hallucinations = [
            "sessiz", "sessizlik", "altyazı", "çeviri", "müzik", 
            "alkış", "izlediğiniz için", "teşekkürler"
        ]

    def clean(self, text: str) -> str | None:
        if not text:
            return None

        original_text = text.strip()
        
        # Normalise, preserving Turkish I/İ: SESSİZ → sessiz (I→ı, İ→i)
        norm_text = original_text.replace("İ", "i").replace("I", "ı").lower()

        # Strip punctuation only for the hallucination check.
        clean_text = re.sub(r'[.,!?]', '', norm_text).strip()

        for h in self.hallucinations:
            if h in clean_text:
                return None
        
        return original_text
