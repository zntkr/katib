import pytest
from core.transcription_filter import TranscriptionFilter

def test_filter_cleans_hallucinations():
    f = TranscriptionFilter()
    # "Sessiz." is a hallucination and should return None
    assert f.clean("Sessiz.") is None
    assert f.clean("İzlediğiniz için teşekkürler.") is None
    assert f.clean("Altyazı: Müzik") is None

def test_filter_preserves_valid_text():
    f = TranscriptionFilter()
    assert f.clean("Merhaba, bugün hava çok güzel.") == "Merhaba, bugün hava çok güzel."

def test_filter_handles_turkish_casing():
    f = TranscriptionFilter()
    # İ -> i, I -> ı conversion must not break during lowercasing
    # If "SESSİZ" (uppercase) is received, it should also be filtered out
    assert f.clean("SESSİZ") is None
    assert f.clean("IŞIK") == "IŞIK"

def test_filter_uppercase_altyazi():
    f = TranscriptionFilter()
    # "ALTYAZI" → replace("I","ı") → "ALTYAZı" → lower → "altyazı" → should match
    # casefold() would be WRONG here: "altyazi" != "altyazı"
    assert f.clean("ALTYAZI") is None

def test_filter_uppercase_sessizlik():
    f = TranscriptionFilter()
    # "SESSİZLİK" → replace("İ","i") → "SESSiZLiK" → lower → "sessizlik" → should match
    assert f.clean("SESSİZLİK") is None

def test_filter_preserves_original_text_unchanged():
    f = TranscriptionFilter()
    # Normalization is only applied for matching; the returned text must be the original
    original = "Merhaba İstanbul"
    result = f.clean(original)
    assert result is original
