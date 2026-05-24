[English](README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [日本語](README.ja.md) · [中文](README.zh.md) · [한국어](README.ko.md) · [العربية](README.ar.md)

# Katib

**Dictado de voz sin conexión para Windows. Mantén una tecla pulsada, habla, suéltala — el texto aparece en tu cursor.**

Sin nube. Sin suscripción. Nada sale de tu equipo.

---

<p align="center">
  <img src="docs/demo.gif" alt="Hold F9, speak, release — text appears" width="800">
</p>

---

## Cómo funciona

1. Haz clic en cualquier campo de texto — navegador, Word, IDE, chat, en cualquier lugar de Windows
2. Mantén pulsada tu tecla de acceso rápido (por defecto **F9**), habla y suéltala
3. Tus palabras son transcritas localmente por [Whisper](https://github.com/openai/whisper) y escritas en el cursor

No se necesita conexión a internet tras la descarga inicial del modelo.

---

## Características

- **100% sin conexión** — Whisper se ejecuta íntegramente en tu CPU, sin claves de API ni cuentas
- **Funciona en cualquier lugar** — cualquier campo de texto enfocable en cualquier aplicación de Windows
- **Pulsar para hablar** — mantén para grabar, suelta para transcribir; sin activaciones accidentales
- **Cinco tamaños de modelo** — de 150 MB a 3 GB; elige entre velocidad y precisión según tu hardware
- **18 idiomas de transcripción** — árabe, chino, inglés, francés, alemán, griego, hindi, indonesio, italiano, japonés, coreano, persa, portugués, ruso, español, turco, urdu y detección automática
- **11 idiomas de interfaz** — English, Türkçe, Deutsch, Español, Français, Português, Русский, 日本語, 中文, 한국어, العربية — con soporte completo de diseño RTL
- **Prompts de IA por idioma** — define el contexto por idioma de voz; se carga automáticamente al cambiar
- **Sin telemetría** — sin análisis, sin informes de fallos, sin comprobaciones de actualizaciones

---

## Instalación

### Opción A — Binario precompilado (recomendado)

Descarga la última versión desde la página de [Releases](../../releases), descomprime y ejecuta `Katib.exe`.

> **Windows SmartScreen** puede mostrar una advertencia porque el binario no está firmado. Haz clic en **Más información → Ejecutar de todas formas**.

### Opción B — Desde el código fuente

Requiere Python 3.10+

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

---

## Modelos

| Modelo | Tamaño | Velocidad | Precisión | Notas |
|--------|--------|-----------|-----------|-------|
| tiny | ~150 MB | Muy rápida | Baja | Hardware modesto o antiguo |
| base | ~300 MB | Rápida | Aceptable | |
| **small** | **~500 MB** | **Equilibrada** | **Buena** | **Punto de partida recomendado** |
| medium | ~1.5 GB | Lenta | Alta | Contenido técnico, acentos |
| large-v3 | ~3 GB | Muy lenta | Máxima | La mayor precisión posible |

Los modelos se descargan desde [Hugging Face (Systran)](https://huggingface.co/Systran) y se almacenan localmente. También puedes indicarle a Katib una carpeta que contenga un modelo que ya hayas descargado.

---

## Configuración

| Ajuste | Descripción |
|--------|-------------|
| **Tecla de acceso rápido** | Cualquier tecla o combinación. Por defecto: F9 |
| **Idioma de voz** | Fuerza un idioma específico o usa la detección automática |
| **Precisión** | `int8` (por defecto) · `int8_float32` · `float32` — velocidad frente a precisión |
| **Prompt de IA** | Contexto enviado a Whisper en cada transcripción; guardado por separado según el idioma de voz |
| **Idioma de la aplicación** | Idioma de la interfaz — cambia al instante, sin necesidad de reiniciar |

---

## Privacidad

Katib está diseñado para funcionar en entornos sin acceso a internet:

- Sin conexiones salientes en tiempo de ejecución
- Sin estadísticas de uso, informes de errores ni comprobaciones de actualizaciones
- La configuración y los registros se almacenan localmente en `%LOCALAPPDATA%\Katib`
- La única actividad de red es la descarga opcional del modelo, que se realiza una sola vez

---

## Compilar desde el código fuente

```bash
pip install pyinstaller
pyinstaller Katib.spec
```

Resultado: `dist/Katib/Katib.exe`

---

## Contribuciones

Las solicitudes de cambios son bienvenidas. Para cambios significativos, abre primero un issue para debatir el enfoque.

Las decisiones de arquitectura están documentadas en [`docs/adr/`](docs/adr/).

---

*Katib (كاتب) — escriba en árabe.*

**Licencia:** MIT
