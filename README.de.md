[English](README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [日本語](README.ja.md) · [中文](README.zh.md) · [한국어](README.ko.md) · [العربية](README.ar.md)

# Katib

**Offline-Sprachdiktat für Windows. Taste halten, sprechen, loslassen — Text erscheint am Cursor.**

Keine Cloud. Kein Abo. Nichts verlässt deinen Rechner.

---

<p align="center">
  <img src="docs/demo.gif" alt="Hold F9, speak, release — text appears" width="800">
</p>

---

## So funktioniert es

1. Klicke in ein beliebiges Textfeld — Browser, Word, IDE, Chat, überall in Windows
2. Halte deine Schnelltaste gedrückt (Standard: **F9**), sprich, lass los
3. Deine Worte werden lokal von [Whisper](https://github.com/openai/whisper) transkribiert und an der Cursorposition eingefügt

Nach dem einmaligen Modell-Download ist keine Internetverbindung mehr erforderlich.

---

## Funktionen

- **100% offline** — Whisper läuft vollständig auf deiner CPU; keine API-Schlüssel, keine Konten nötig
- **Funktioniert überall** — jedes fokussierbare Textfeld in jeder Windows-Anwendung
- **Push-to-Talk** — halten zum Aufnehmen, loslassen zum Transkribieren; keine versehentlichen Auslöser
- **Fünf Modellgrößen** — 150 MB bis 3 GB; Geschwindigkeit und Genauigkeit je nach Hardware abstimmbar
- **18 Transkriptionssprachen** — Arabisch, Chinesisch, Englisch, Französisch, Deutsch, Griechisch, Hindi, Indonesisch, Italienisch, Japanisch, Koreanisch, Persisch, Portugiesisch, Russisch, Spanisch, Türkisch, Urdu sowie automatische Erkennung
- **11 Oberflächensprachen** — English, Türkçe, Deutsch, Español, Français, Português, Русский, 日本語, 中文, 한국어, العربية — mit vollständiger RTL-Layout-Unterstützung
- **Sprachspezifische AI-Prompts** — lege je Sprache einen Kontext fest; wird beim Wechsel automatisch geladen
- **Keine Telemetrie** — keine Analysedaten, keine Fehlerberichte, keine Update-Abfragen

---

## Installation

### Option A — Vorgefertigte Binärdatei (empfohlen)

Lade die neueste Version von der [Releases](../../releases)-Seite herunter, entpacke das Archiv und starte `Katib.exe`.

> **Windows SmartScreen** kann eine Warnung anzeigen, da die Datei nicht signiert ist. Klicke auf **Weitere Informationen → Trotzdem ausführen**.

### Option B — Aus dem Quellcode

Erfordert Python 3.10 oder höher

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

---

## Modelle

| Modell | Größe | Geschwindigkeit | Genauigkeit | Hinweise |
|--------|-------|-----------------|-------------|----------|
| tiny | ~150 MB | Sehr schnell | Niedrig | Ältere oder schwächere Hardware |
| base | ~300 MB | Schnell | Ausreichend | |
| **small** | **~500 MB** | **Ausgewogen** | **Gut** | **Empfohlener Einstieg** |
| medium | ~1,5 GB | Langsam | Hoch | Fachlicher Inhalt, Akzente |
| large-v3 | ~3 GB | Sehr langsam | Maximum | Bestmögliche Genauigkeit |

Modelle werden von [Hugging Face (Systran)](https://huggingface.co/Systran) geladen und lokal gespeichert. Du kannst Katib auch auf einen Ordner verweisen, der ein bereits heruntergeladenes Modell enthält.

---

## Einstellungen

| Einstellung | Beschreibung |
|-------------|--------------|
| **Schnelltaste** | Beliebige Taste oder Kombination. Standard: F9 |
| **Spracheingabesprache** | Eine bestimmte Sprache erzwingen oder automatische Erkennung verwenden |
| **Präzision** | `int8` (Standard) · `int8_float32` · `float32` — Abwägung zwischen Geschwindigkeit und Genauigkeit |
| **AI-Prompt** | Kontext, der Whisper je Transkription übergeben wird; wird separat je Spracheingabesprache gespeichert |
| **App-Sprache** | Oberflächensprache — wechselt sofort, kein Neustart erforderlich |

---

## Datenschutz

Katib ist für den Betrieb ohne Netzwerkverbindung ausgelegt:

- Keine ausgehenden Verbindungen zur Laufzeit
- Keine Nutzungsstatistiken, Fehlerberichte oder Update-Abfragen
- Einstellungen und Protokolle werden lokal unter `%LOCALAPPDATA%\Katib` gespeichert
- Die einzige Netzwerkaktivität ist der optionale einmalige Modell-Download

---

## Aus dem Quellcode erstellen

```bash
pip install pyinstaller
pyinstaller Katib.spec
```

Ausgabe: `dist/Katib/Katib.exe`

---

## Mitwirken

Pull Requests sind willkommen. Bei wesentlichen Änderungen bitte zuerst ein Issue eröffnen, um den Ansatz zu besprechen.

Architekturentscheidungen sind in [`docs/adr/`](docs/adr/) dokumentiert.

---

*Katib (كاتب) — Arabisch für Schreiber.*

**Lizenz:** MIT
