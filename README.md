# Katib

**Offline AI dictation for Windows. Press a key, speak, release — text appears wherever your cursor is.**

No cloud. No subscription. No data ever leaves your machine.

---

## How it works

1. Click any text field in any app
2. Hold your hotkey (default: **F9**), speak, release
3. Your words appear at the cursor — transcribed locally on your CPU

That's it. Nothing is sent anywhere.

---

## Features

- **100% offline** — transcription runs entirely on your machine after the one-time model download
- **Works everywhere** — any text field in any Windows app (browser, Word, Notepad, IDE, chat)
- **Push-to-talk** — hold to record, release to transcribe; no accidental activation
- **Five model sizes** — from 150 MB (fast) to 3 GB (maximum accuracy), pick what fits your hardware
- **Built-in downloader** — one click to download a model directly from within the app
- **18 transcription languages** — Arabic, Chinese, English, French, German, Greek, Hindi, Indonesian, Italian, Japanese, Korean, Persian, Portuguese, Russian, Spanish, Turkish, Urdu, and auto-detect
- **10 UI languages** — English, Türkçe, Deutsch, Español, Français, Português, Русский, 日本語, 中文, 한국어
- **AI prompt** — give the model context ("This is a medical report.") for improved accuracy on specialized vocabulary
- **System tray** — lives in the background, zero window clutter
- **No telemetry** — no analytics, no crash reporting, no update pings

---

## Installation

### Option A — Download (recommended)

Download the latest release from the [Releases](../../releases) page, unzip, and run `Katib.exe`. No Python or dependencies required.

> **Windows SmartScreen:** If you see a "Windows protected your PC" warning, click **More info → Run anyway**. This appears because the executable is not yet code-signed.

### Option B — Run from source

**Requirements:** Python 3.10+

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

---

## Models

| Model | Size | Speed | Accuracy | Best for |
|-------|------|-------|----------|----------|
| tiny | ~150 MB | Very fast | Low | Old or low-power PCs |
| base | ~300 MB | Fast | Decent | Everyday use on modest hardware |
| **small** | **~500 MB** | **Balanced** | **Good** | **Recommended starting point** |
| medium | ~1.5 GB | Slow | High | High-end hardware, technical content |
| large-v3 | ~3 GB | Very slow | Maximum | Best possible accuracy |

Models are downloaded from [Hugging Face](https://huggingface.co/Systran) and stored locally. You can also point Katib to a folder containing a model you already have.

---

## Settings

| Setting | Description |
|---------|-------------|
| **Hotkey** | Any key or combination. Default: F9 |
| **Speech language** | Force a specific language or use Auto Detect |
| **Precision** | `int8` (fast, default), `int8_float32` (balanced), `float32` (slow, most accurate) |
| **AI prompt** | Optional context string passed to the model on every transcription |
| **App language** | Changes the UI language; requires restart |

---

## Privacy

Katib is designed to be **air-gapped friendly**:

- No outbound network connections at runtime
- No usage statistics, no error reporting, no update checks
- Settings and logs are stored locally under `%APPDATA%\Katib`
- The only network activity is the one-time model download from Hugging Face (optional — you can supply your own model folder)

---

## Building from source

```bash
pip install pyinstaller
pyinstaller Katib.spec
```

Output: `dist/Katib/Katib.exe`

---

## Contributing

Pull requests are welcome. For significant changes, open an issue first to discuss what you'd like to change.

Architecture decisions are documented in [`docs/adr/`](docs/adr/).

---

## License

MIT
