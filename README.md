<div align="center">
  <img src="docs/logo.png" alt="Katib" width="120">
  <h1>Katib</h1>
  <p>Offline voice dictation. Hold a key, speak, release — text appears at your cursor.</p>

  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-0078d7.svg?logo=windows)](https://github.com/zntkr/katib/releases)
</div>

---

Cloud dictation tools are convenient — until you think about what you're actually sending. Your medical notes, legal drafts, personal messages, all of it goes to someone's server. Katib doesn't do that. It runs [Whisper](https://github.com/openai/whisper) entirely on your machine, works in any text field, and never touches the internet at runtime.

<p align="center">
  <img src="docs/demo.gif" alt="Hold F9, speak, release — text appears" width="800">
</p>

## Install

Download the latest release from the [Releases](../../releases) page, unzip, run `Katib.exe`.

> **Windows SmartScreen** may show a warning because the binary is unsigned. Click **More info → Run anyway**.

## How it works

1. Click any text field — browser, Word, IDE, chat, anywhere
2. Hold your hotkey (default **F9**), speak, release
3. Your words appear at the cursor

No internet required after the one-time model download.

## What it does

- **100% offline** — no API keys, no accounts, no subscription
- **Works everywhere** — any focusable text field in any application
- **Push-to-talk** — hold to record, release to transcribe; no accidental triggers
- **Five model sizes** — 150 MB to 3 GB; trade speed for accuracy on your hardware
- **18 transcription languages** — Arabic, Chinese, English, French, German, Greek, Hindi, Indonesian, Italian, Japanese, Korean, Persian, Portuguese, Russian, Spanish, Turkish, Urdu, and auto-detect
- **11 UI languages** — English, Türkçe, Deutsch, Español, Français, Português, Русский, 日本語, 中文, 한국어, العربية — with full RTL layout support
- **No telemetry** — no analytics, no crash reporting, no update pings

## What it doesn't do

- Work on macOS — not supported
- Transcribe in real-time — it processes after you release the key
- Accept voice commands or edit by voice — dictation only

## Models

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | ~150 MB | Very fast | Low |
| base | ~300 MB | Fast | Fair |
| **small** | **~500 MB** | **Balanced** | **Good** |
| medium | ~1.5 GB | Slow | High |
| large-v3 | ~3 GB | Very slow | Maximum |

**small** is the recommended starting point. Models are downloaded once from [Hugging Face](https://huggingface.co/Systran) and stored locally.

## Settings

| Setting | Description |
|---------|-------------|
| **Hotkey** | Any key or combination. Default: F9 |
| **Speech language** | Force a specific language or use Auto Detect |
| **Precision** | `int8` (default) · `int8_float32` · `float32` — speed vs. accuracy |
| **AI prompt** | Context passed to Whisper per transcription; saved per speech language |
| **App language** | UI language — changes instantly, no restart needed |

---

## Platform support

| Platform | Status | Notes |
|----------|--------|-------|
| Windows 10/11 | ✅ Full support | Pre-built binary available |
| Linux (X11) | ✅ Supported | Run from source; requires an X11 session |
| Linux (Wayland) | ⚠️ Partial | UI and transcription work; global hotkey unavailable — log in with "Ubuntu on Xorg" |
| macOS | ❌ Not supported | — |

---

## Contributing

PRs welcome. For significant changes, open an issue first. Architecture decisions are in [`docs/adr/`](docs/adr/).

## From source

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

```bash
# Build
pip install pyinstaller
pyinstaller Katib.spec
```

---

<sub>*Katib (كاتب) — Arabic for scribe.* · MIT License</sub>
