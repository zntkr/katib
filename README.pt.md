[English](README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [日本語](README.ja.md) · [中文](README.zh.md) · [한국어](README.ko.md) · [العربية](README.ar.md)

# Katib

**Ditado por voz offline para Windows. Segure uma tecla, fale, solte — o texto aparece no cursor.**

Sem nuvem. Sem assinatura. Nada sai do seu computador.

---

<p align="center">
  <img src="docs/demo.gif" alt="Hold F9, speak, release — text appears" width="800">
</p>

---

## Como funciona

1. Clique em qualquer campo de texto — navegador, Word, IDE, chat, em qualquer lugar no Windows
2. Segure a tecla de atalho (padrão **F9**), fale, solte
3. Suas palavras são transcritas localmente pelo [Whisper](https://github.com/openai/whisper) e digitadas no cursor

Sem internet necessária após o download único do modelo.

---

## Funcionalidades

- **100% offline** — Whisper roda inteiramente no seu CPU, sem chaves de API, sem contas
- **Funciona em qualquer lugar** — qualquer campo de texto focável em qualquer aplicativo Windows
- **Push-to-talk** — segure para gravar, solte para transcrever; sem acionamentos acidentais
- **Cinco tamanhos de modelo** — 150 MB a 3 GB; equilibre velocidade e precisão conforme seu hardware
- **18 idiomas de transcrição** — Árabe, Chinês, Inglês, Francês, Alemão, Grego, Hindi, Indonésio, Italiano, Japonês, Coreano, Persa, Português, Russo, Espanhol, Turco, Urdu e detecção automática
- **11 idiomas de interface** — English, Türkçe, Deutsch, Español, Français, Português, Русский, 日本語, 中文, 한국어, العربية — com suporte completo a layout RTL
- **Prompts de IA por idioma** — defina contexto por idioma de fala; carregado automaticamente ao trocar
- **Sem telemetria** — sem análises, sem relatórios de erros, sem verificações de atualização

---

## Instalação

### Opção A — Binário pré-compilado (recomendado)

Baixe a versão mais recente na página de [Releases](../../releases), descompacte e execute `Katib.exe`.

> **Windows SmartScreen** pode exibir um aviso porque o binário não é assinado. Clique em **Mais informações → Executar assim mesmo**.

### Opção B — A partir do código-fonte

Requer Python 3.10+

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

---

## Modelos

| Modelo | Tamanho | Velocidade | Precisão | Observações |
|--------|---------|------------|----------|-------------|
| tiny | ~150 MB | Muito rápida | Baixa | Hardware de entrada ou mais antigo |
| base | ~300 MB | Rápida | Razoável | |
| **small** | **~500 MB** | **Equilibrada** | **Boa** | **Ponto de partida recomendado** |
| medium | ~1,5 GB | Lenta | Alta | Conteúdo técnico, sotaques |
| large-v3 | ~3 GB | Muito lenta | Máxima | Melhor precisão possível |

Os modelos são obtidos do [Hugging Face (Systran)](https://huggingface.co/Systran) e armazenados localmente. Você também pode apontar o Katib para uma pasta que contenha um modelo já baixado.

---

## Configurações

| Configuração | Descrição |
|--------------|-----------|
| **Hotkey** | Qualquer tecla ou combinação. Padrão: F9 |
| **Idioma de fala** | Force um idioma específico ou use Detecção Automática |
| **Precisão** | `int8` (padrão) · `int8_float32` · `float32` — velocidade vs. precisão |
| **Prompt de IA** | Contexto enviado ao Whisper por transcrição; salvo separadamente por idioma de fala |
| **Idioma do app** | Idioma da interface — muda instantaneamente, sem necessidade de reiniciar |

---

## Privacidade

O Katib foi projetado para ser amigável a ambientes isolados:

- Sem conexões de saída durante a execução
- Sem estatísticas de uso, relatórios de erros ou verificações de atualização
- Configurações e logs armazenados localmente em `%LOCALAPPDATA%\Katib`
- A única atividade de rede é o download único e opcional do modelo

---

## Compilando a partir do código-fonte

```bash
pip install pyinstaller
pyinstaller Katib.spec
```

Saída: `dist/Katib/Katib.exe`

---

## Contribuindo

Pull requests são bem-vindos. Para mudanças significativas, abra uma issue primeiro para discutir a abordagem.

As decisões de arquitetura estão documentadas em [`docs/adr/`](docs/adr/).

---

*Katib (كاتب) — árabe para escriba.*

**Licença:** MIT
