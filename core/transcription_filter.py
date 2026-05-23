import re

class TranscriptionFilter:
    """Whisper halüsinasyonlarını temizleyen ve metni normalize eden derin modül."""
    
    def __init__(self):
        # Whisper'ın gürültü duyduğunda uydurduğu tipik kelimeler
        self.hallucinations = [
            "sessiz", "sessizlik", "altyazı", "çeviri", "müzik", 
            "alkış", "izlediğiniz için", "teşekkürler"
        ]

    def clean(self, text: str) -> str | None:
        if not text:
            return None

        original_text = text.strip()
        
        # 1. Normalizasyon (Türkçe I/İ karakterlerini koruyarak)
        # SESSİZ -> sessiz (I -> ı, İ -> i)
        norm_text = original_text.replace("İ", "i").replace("I", "ı").lower()
        
        # Noktalama işaretlerini temizle (sadece halüsinasyon kontrolü için)
        clean_text = re.sub(r'[.,!?]', '', norm_text).strip()

        # 2. Halüsinasyon Kontrolü
        for h in self.hallucinations:
            if h in clean_text:
                return None
        
        return original_text
