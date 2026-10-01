"""
Katib ölçüm betiği (plan 0007).

Kendi kayıtlarınızı uygulamanın gerçek karar zincirinden geçirir ve her
sessizlik katmanının neyi elediğini sayar:

    1. süre      — MIN_RECORDING_DURATION'dan kısa kayıt (workers/audio_worker.py)
    2. seviye    — core.audio_analysis.is_silent
    3. whisper   — Whisper'ın boş döndürdüğü kayıt (vad_filter, no_speech_threshold)
    4. filtre    — core.transcription_filter (uydurma kalıplar)

Hazırlık: `olcum/` klasörüne kısa WAV kayıtları (16-bit PCM) ve her birinin
yanına aynı adlı bir .txt koyun: içinde söylediğiniz metin. Konuşmasız kayıt
(yanlışlıkla basış, ortam sesi) için .txt'yi BOŞ bırakın.

🛑 `olcum/` kendi sesinizdir, kişisel veridir: `.gitignore`'dadır, depoya
girmez. Rapor dikte metnini varsayılan olarak göstermez (--metin ile gösterir).

Kullanım (proje kökünden):

    python scripts/olcum.py
    python scripts/olcum.py --min-sure 0.2 --no-seviye --no-vad   # katmanları kapatıp karşılaştır
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.audio_analysis import analyse_vad, is_silent  # noqa: E402
from core.transcription_filter import TranscriptionFilter  # noqa: E402
from workers.audio_worker import MIN_RECORDING_DURATION, SAMPLE_RATE, _resample  # noqa: E402
from workers.transcription_worker import TRANSCRIBE_OPTIONS  # noqa: E402

# The app measures level per PortAudio block of 1024 samples; at 16 kHz that is 64 ms.
CHUNK = 1024
KATMANLAR = ("sure", "seviye", "whisper_bos", "filtre")


@dataclass
class Ayarlar:
    min_sure: float = MIN_RECORDING_DURATION
    silence_db: float = -55.0
    seviye: bool = True         # False: katman 2 tamamen kapalı (sesli süre kuralı dahil)
    vad: bool = True
    dil: str | None = None
    prompt: str = ""


@dataclass
class Sonuc:
    dosya: str
    konusma_var: bool
    katman: str | None          # elendiği katman; None = yazıya döküldü
    wer: float | None           # yalnız konuşmalı kayıtta
    whisper_ms: float | None
    metin: str


def wav_oku(path: Path) -> np.ndarray:
    """16-bit PCM WAV → mono float32, 16 kHz."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path.name}: yalnız 16-bit PCM WAV desteklenir")
        channels, rate = w.getnchannels(), w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    audio = pcm.astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return _resample(audio, rate, SAMPLE_RATE).astype(np.float32)


def _kelimeler(text: str) -> list[str]:
    text = text.replace("I", "ı").replace("İ", "i").lower()
    return re.sub(r"[^\w\s]", "", text).split()


def kelime_hata_orani(beklenen: str, cikan: str) -> float:
    """Word error rate: (substitutions + insertions + deletions) / reference words.
    Case and punctuation are ignored; Turkish diacritics count."""
    ref, hyp = _kelimeler(beklenen), _kelimeler(cikan)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def degerlendir(audio: np.ndarray, model, ayarlar: Ayarlar,
                filtre: TranscriptionFilter | None = None) -> tuple[str | None, str, float | None]:
    """The app's decision chain for one recording → (elendiği katman | None, metin, whisper ms)."""
    duration = len(audio) / SAMPLE_RATE
    if duration < ayarlar.min_sure:
        return "sure", "", None

    rms = [float(np.sqrt(np.mean(audio[i:i + CHUNK] ** 2))) for i in range(0, len(audio), CHUNK)]
    if ayarlar.seviye and is_silent(analyse_vad(rms, CHUNK / SAMPLE_RATE), silence_db=ayarlar.silence_db):
        return "seviye", "", None

    options = dict(TRANSCRIBE_OPTIONS, vad_filter=ayarlar.vad)
    start = time.perf_counter()
    segments, _ = model.transcribe(audio, language=ayarlar.dil, initial_prompt=ayarlar.prompt, **options)
    text = " ".join(seg.text for seg in segments).strip()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    if not text:
        return "whisper_bos", "", elapsed_ms
    if (filtre or TranscriptionFilter()).clean(text, duration=duration) is None:
        return "filtre", text, elapsed_ms
    return None, text, elapsed_ms


def olc(klasor: Path, model, ayarlar: Ayarlar) -> list[Sonuc]:
    filtre = TranscriptionFilter()
    sonuclar = []
    for wav in sorted(Path(klasor).glob("*.wav")):
        txt = wav.with_suffix(".txt")
        if not txt.exists():
            print(f"⚠️  {wav.name}: yanında {txt.name} yok, atlandı", file=sys.stderr)
            continue
        beklenen = txt.read_text(encoding="utf-8").strip()
        katman, metin, ms = degerlendir(wav_oku(wav), model, ayarlar, filtre)
        wer = kelime_hata_orani(beklenen, metin if katman is None else "") if beklenen else None
        sonuclar.append(Sonuc(wav.name, bool(beklenen), katman, wer, ms, metin))
    return sonuclar


def rapor(sonuclar: list[Sonuc], metin_goster: bool = False) -> str:
    satirlar = [f"{'dosya':28} {'beklenen':9} {'sonuç':12} {'WER':>6} {'whisper ms':>10}"]
    for s in sonuclar:
        sonuc = "yazıldı" if s.katman is None else f"elendi:{s.katman}"
        wer = "" if s.wer is None else f"{s.wer:.0%}"
        ms = "" if s.whisper_ms is None else f"{s.whisper_ms:.0f}"
        satir = f"{s.dosya:28} {'konuşma' if s.konusma_var else 'boş':9} {sonuc:12} {wer:>6} {ms:>10}"
        if metin_goster and s.metin:
            satir += f"  {s.metin!r}"
        satirlar.append(satir)

    konusmali = [s for s in sonuclar if s.konusma_var]
    bos = [s for s in sonuclar if not s.konusma_var]
    elenen = [s for s in konusmali if s.katman is not None]
    satirlar += ["", f"Konuşmalı kayıt: {len(konusmali)} · elenen: {len(elenen)}"]
    for k in KATMANLAR:
        n = sum(1 for s in elenen if s.katman == k)
        if n:
            satirlar.append(f"    {k}: {n}")
    if konusmali:
        satirlar.append(f"    ortalama WER (elenen = %100): {np.mean([s.wer for s in konusmali]):.1%}")
    gecen = [s for s in bos if s.katman is None]
    satirlar.append(f"Konuşmasız kayıt: {len(bos)} · uydurma metin yapıştırılırdı: {len(gecen)}")
    sureler = [s.whisper_ms for s in sonuclar if s.whisper_ms is not None]
    if sureler:
        satirlar.append(f"Ortalama Whisper süresi: {np.mean(sureler):.0f} ms")
    return "\n".join(satirlar)


def main(argv: list[str] | None = None) -> int:
    from core.settings import SettingsManager, DEFAULT_DOWNLOAD_PARENT
    from core.models import ModelProvider

    settings = SettingsManager()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--klasor", type=Path, default=ROOT / "olcum")
    p.add_argument("--model", help="model klasörü (varsayılan: uygulamanın seçili modeli)")
    p.add_argument("--dil", default=settings.get("language"), help="ör. tr; boşsa otomatik algılama")
    p.add_argument("--min-sure", type=float, default=MIN_RECORDING_DURATION)
    p.add_argument("--silence-db", type=float, default=-55.0)
    p.add_argument("--no-seviye", action="store_true", help="katman 2'yi (seviye analizi) tamamen kapat")
    p.add_argument("--no-vad", action="store_true", help="Whisper'ın vad_filter'ını kapat")
    p.add_argument("--metin", action="store_true", help="raporda dikte metnini göster")
    args = p.parse_args(argv)

    if not args.klasor.is_dir() or not any(args.klasor.glob("*.wav")):
        print(f"{args.klasor} içinde WAV yok. Hazırlık için: python scripts/olcum.py --help")
        return 1
    model_dir = args.model or ModelProvider(DEFAULT_DOWNLOAD_PARENT, settings.get("model_dir")).get_active_model_path()
    if not model_dir:
        print("Model bulunamadı; --model ile klasörü verin.")
        return 1

    from faster_whisper import WhisperModel
    print(f"Model: {model_dir}")
    model = WhisperModel(model_dir, device="cpu", compute_type=settings.get("compute_type"), local_files_only=True)
    ayarlar = Ayarlar(min_sure=args.min_sure, silence_db=args.silence_db, seviye=not args.no_seviye,
                      vad=not args.no_vad, dil=args.dil or None,
                      prompt=(settings.get("initial_prompt") or "").strip())
    print(rapor(olc(args.klasor, model, ayarlar), metin_goster=args.metin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
