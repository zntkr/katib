[English](README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [日本語](README.ja.md) · [中文](README.zh.md) · [한국어](README.ko.md) · [العربية](README.ar.md)

# Katib

**Dictée vocale hors ligne pour Windows. Maintenez une touche, parlez, relâchez — le texte apparaît à votre curseur.**

Pas de cloud. Pas d'abonnement. Rien ne quitte votre machine.

---

<p align="center">
  <img src="docs/demo.gif" alt="Hold F9, speak, release — text appears" width="800">
</p>

---

## Comment ça fonctionne

1. Cliquez dans n'importe quel champ de texte — navigateur, Word, IDE, messagerie, n'importe où sous Windows
2. Maintenez votre raccourci clavier (par défaut **F9**), parlez, relâchez
3. Vos mots sont transcrits localement par [Whisper](https://github.com/openai/whisper) et saisis à l'emplacement du curseur

Aucune connexion internet requise après le téléchargement initial du modèle.

---

## Fonctionnalités

- **100% hors ligne** — Whisper s'exécute entièrement sur votre CPU, sans clé API ni compte requis
- **Fonctionne partout** — tout champ de texte focalisable dans n'importe quelle application Windows
- **Appuyer pour parler** — maintenez pour enregistrer, relâchez pour transcrire ; pas de déclenchements accidentels
- **Cinq tailles de modèle** — de 150 Mo à 3 Go ; choisissez entre vitesse et précision selon votre matériel
- **18 langues de transcription** — arabe, chinois, anglais, français, allemand, grec, hindi, indonésien, italien, japonais, coréen, persan, portugais, russe, espagnol, turc, ourdou et détection automatique
- **11 langues d'interface** — English, Türkçe, Deutsch, Español, Français, Português, Русский, 日本語, 中文, 한국어, العربية — avec prise en charge complète de la mise en page RTL
- **Prompts IA par langue** — définissez un contexte par langue de dictée ; chargé automatiquement lors du changement
- **Aucune télémétrie** — pas d'analyse, pas de rapport de plantage, pas de vérification de mises à jour

---

## Installation

### Option A — Binaire précompilé (recommandé)

Téléchargez la dernière version depuis la page [Releases](../../releases), décompressez et lancez `Katib.exe`.

> **Windows SmartScreen** peut afficher un avertissement car le binaire n'est pas signé. Cliquez sur **Plus d'informations → Exécuter quand même**.

### Option B — Depuis les sources

Nécessite Python 3.10+

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

---

## Modèles

| Modèle | Taille | Vitesse | Précision | Notes |
|--------|--------|---------|-----------|-------|
| tiny | ~150 Mo | Très rapide | Faible | Matériel d'entrée de gamme ou ancien |
| base | ~300 Mo | Rapide | Correcte | |
| **small** | **~500 Mo** | **Équilibrée** | **Bonne** | **Point de départ recommandé** |
| medium | ~1,5 Go | Lente | Élevée | Contenu technique, accents |
| large-v3 | ~3 Go | Très lente | Maximale | Meilleure précision possible |

Les modèles sont téléchargés depuis [Hugging Face (Systran)](https://huggingface.co/Systran) et stockés localement. Vous pouvez aussi indiquer à Katib un dossier contenant un modèle déjà téléchargé.

---

## Paramètres

| Paramètre | Description |
|-----------|-------------|
| **Raccourci clavier** | N'importe quelle touche ou combinaison. Par défaut : F9 |
| **Langue de dictée** | Forcer une langue spécifique ou utiliser la détection automatique |
| **Précision** | `int8` (par défaut) · `int8_float32` · `float32` — vitesse ou précision |
| **Prompt IA** | Contexte transmis à Whisper à chaque transcription ; sauvegardé séparément par langue de dictée |
| **Langue de l'application** | Langue de l'interface — change instantanément, sans redémarrage |

---

## Confidentialité

Katib est conçu pour fonctionner sans accès à internet :

- Aucune connexion sortante à l'exécution
- Aucune statistique d'utilisation, rapport d'erreur ou vérification de mise à jour
- Les paramètres et journaux sont stockés localement dans `%LOCALAPPDATA%\Katib`
- La seule activité réseau est le téléchargement optionnel du modèle, effectué une seule fois

---

## Compilation depuis les sources

```bash
pip install pyinstaller
pyinstaller Katib.spec
```

Résultat : `dist/Katib/Katib.exe`

---

## Contribuer

Les pull requests sont les bienvenues. Pour des changements importants, ouvrez d'abord une issue afin de discuter de l'approche envisagée.

Les décisions d'architecture sont documentées dans [`docs/adr/`](docs/adr/).

---

*Katib (كاتب) — scribe en arabe.*

**Licence :** MIT
