[English](README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [日本語](README.ja.md) · [中文](README.zh.md) · [한국어](README.ko.md) · [العربية](README.ar.md)

# Katib

**Offline voice dictation for Windows and Linux. Hold a key, speak, release — text appears at your cursor.**

No cloud. No subscription. Nothing leaves your machine.

---

<p align="center">
  <img src="docs/demo.gif" alt="Hold F9, speak, release — text appears" width="800">
</p>

---

## How it works

1. Click any text field — browser, Word, IDE, chat, anywhere
2. Hold your hotkey (default **F9**), speak, release
3. Your words are transcribed locally by [Whisper](https://github.com/openai/whisper) and typed at the cursor

No internet required after the one-time model download.

---

## Features

- **100% offline** — Whisper runs entirely on your CPU, no API keys, no accounts
- **Works everywhere** — any focusable text field in any application
- **Push-to-talk** — hold to record, release to transcribe; no accidental triggers
- **Five model sizes** — 150 MB to 3 GB; trade speed for accuracy on your hardware
- **18 transcription languages** — Arabic, Chinese, English, French, German, Greek, Hindi, Indonesian, Italian, Japanese, Korean, Persian, Portuguese, Russian, Spanish, Turkish, Urdu, and auto-detect
- **11 UI languages** — English, Türkçe, Deutsch, Español, Français, Português, Русский, 日本語, 中文, 한국어, العربية — with full RTL layout support
- **Per-language AI prompts** — set context per speech language; loaded automatically on switch
- **No telemetry** — no analytics, no crash reporting, no update pings

---

## Installation

### Windows — Pre-built binary (recommended)

Download the latest release from the [Releases](../../releases) page, unzip, run `Katib.exe`.

> **Windows SmartScreen** may show a warning because the binary is unsigned. Click **More info → Run anyway**.

### Windows & Linux — From source

Requires Python 3.10+

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

---

## Platform support

| Platform | Status | Notes |
|----------|--------|-------|
| Windows 10/11 | ✅ Full support | Pre-built binary available |
| Linux (X11) | ✅ Supported | Run from source; global hotkey requires an X11 session |
| Linux (Wayland) | ⚠️ Partial | UI and transcription work; global hotkey is unavailable due to Wayland security restrictions — log in with "Ubuntu on Xorg" to enable it |
| macOS | ❌ Not supported | — |

---

## Models

| Model | Size | Speed | Accuracy | Notes |
|-------|------|-------|----------|-------|
| tiny | ~150 MB | Very fast | Low | Low-end or older hardware |
| base | ~300 MB | Fast | Fair | |
| **small** | **~500 MB** | **Balanced** | **Good** | **Recommended starting point** |
| medium | ~1.5 GB | Slow | High | Technical content, accents |
| large-v3 | ~3 GB | Very slow | Maximum | Best possible accuracy |

Models are fetched from [Hugging Face (Systran)](https://huggingface.co/Systran) and stored locally. You can also point Katib to a folder containing a model you already downloaded.

---

## Settings

| Setting | Description |
|---------|-------------|
| **Hotkey** | Any key or combination. Default: F9 |
| **Speech language** | Force a specific language or use Auto Detect |
| **Precision** | `int8` (default) · `int8_float32` · `float32` — speed vs. accuracy |
| **AI prompt** | Context passed to Whisper per transcription; saved separately per speech language |
| **App language** | UI language — changes instantly, no restart needed |

---

## Privacy

Katib is designed to be air-gap friendly:

- No outbound connections at runtime
- No usage statistics, error reporting, or update checks
- Settings and logs stored locally — `%LOCALAPPDATA%\Katib` on Windows, `~/.local/share/Katib` on Linux
- The only network activity is the optional one-time model download

---

## Building from source

```bash
pip install pyinstaller
pyinstaller Katib.spec
```

Output: `dist/Katib/Katib.exe`

---

## Contributing

Pull requests are welcome. For significant changes, open an issue first to discuss the approach.

Architecture decisions are documented in [`docs/adr/`](docs/adr/).

---

*Katib (كاتب) — Arabic for scribe.*

**License:** MIT
