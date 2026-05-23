import pytest
from core.transcription_filter import TranscriptionFilter

def test_filter_cleans_hallucinations():
    f = TranscriptionFilter()
    # "Sessiz." bir halüsinasyondur, None dönmeli
    assert f.clean("Sessiz.") is None
    assert f.clean("İzlediğiniz için teşekkürler.") is None
    assert f.clean("Altyazı: Müzik") is None

def test_filter_preserves_valid_text():
    f = TranscriptionFilter()
    assert f.clean("Merhaba, bugün hava çok güzel.") == "Merhaba, bugün hava çok güzel."

def test_filter_handles_turkish_casing():
    f = TranscriptionFilter()
    # İ -> i, I -> ı dönüşümü (lower yaparken bozulmamalı)
    # Eğer "SESSİZ" (büyük harf) gelirse bunu da elemeli
    assert f.clean("SESSİZ") is None
    assert f.clean("IŞIK") == "IŞIK"

def test_filter_uppercase_altyazi():
    f = TranscriptionFilter()
    # "ALTYAZI" → replace("I","ı") → "ALTYAZı" → lower → "altyazı" → eşleşmeli
    # casefold() burada YANLIŞ olurdu: "altyazi" != "altyazı"
    assert f.clean("ALTYAZI") is None

def test_filter_uppercase_sessizlik():
    f = TranscriptionFilter()
    # "SESSİZLİK" → replace("İ","i") → "SESSiZLiK" → lower → "sessizlik" → eşleşmeli
    assert f.clean("SESSİZLİK") is None

def test_filter_preserves_original_text_unchanged():
    f = TranscriptionFilter()
    # Normalizasyon sadece eşleşme için yapılır; dönen metin orijinal olmalı
    original = "Merhaba İstanbul"
    result = f.clean(original)
    assert result is original
