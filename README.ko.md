[English](README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [日本語](README.ja.md) · [中文](README.zh.md) · [한국어](README.ko.md) · [العربية](README.ar.md)

# Katib

**Windows용 오프라인 음성 받아쓰기. 키를 누르고, 말하고, 놓으면 — 커서 위치에 텍스트가 입력됩니다.**

클라우드 없음. 구독 없음. 어떤 데이터도 기기 밖으로 나가지 않습니다.

---

<p align="center">
  <img src="docs/demo.gif" alt="Hold F9, speak, release — text appears" width="800">
</p>

---

## 작동 방식

1. 임의의 텍스트 필드를 클릭하세요 — 브라우저, Word, IDE, 채팅 앱 등 Windows 어디서든 가능합니다
2. 단축키(기본값 **F9**)를 누른 채 말하고, 놓으세요
3. [Whisper](https://github.com/openai/whisper)가 로컬에서 음성을 텍스트로 변환해 커서 위치에 입력합니다

최초 모델 다운로드 후에는 인터넷 연결이 필요 없습니다.

---

## 기능

- **100% 오프라인** — Whisper가 완전히 CPU에서 실행되며, API 키나 계정이 필요 없습니다
- **어디서나 작동** — Windows의 모든 애플리케이션에서 포커스 가능한 텍스트 필드 지원
- **푸시-투-토크** — 누르면 녹음, 놓으면 변환; 의도치 않은 실행 없음
- **5가지 모델 크기** — 150 MB에서 3 GB까지; 하드웨어에 맞게 속도와 정확도를 조절 가능
- **18개 전사 언어** — 아랍어, 중국어, 영어, 프랑스어, 독일어, 그리스어, 힌디어, 인도네시아어, 이탈리아어, 일본어, 한국어, 페르시아어, 포르투갈어, 러시아어, 스페인어, 터키어, 우르두어, 자동 감지
- **11개 UI 언어** — English, Türkçe, Deutsch, Español, Français, Português, Русский, 日本語, 中文, 한국어, العربية — 완전한 RTL 레이아웃 지원 포함
- **언어별 AI 프롬프트** — 음성 언어별로 문맥 설정 가능; 언어 전환 시 자동으로 불러옴
- **텔레메트리 없음** — 분석, 오류 보고, 업데이트 확인 일체 없음

---

## 설치

### 옵션 A — 사전 빌드된 실행 파일 (권장)

[Releases](../../releases) 페이지에서 최신 릴리즈를 다운로드하고, 압축을 풀어 `Katib.exe`를 실행하세요.

> **Windows SmartScreen**이 경고를 표시할 수 있습니다. 실행 파일에 서명이 없기 때문입니다. **추가 정보 → 실행**을 클릭하세요.

### 옵션 B — 소스에서 빌드

Python 3.10 이상 필요

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

---

## 모델

| 모델 | 크기 | 속도 | 정확도 | 비고 |
|------|------|------|--------|------|
| tiny | ~150 MB | 매우 빠름 | 낮음 | 저사양 또는 구형 하드웨어 |
| base | ~300 MB | 빠름 | 보통 | |
| **small** | **~500 MB** | **균형** | **좋음** | **권장 시작점** |
| medium | ~1.5 GB | 느림 | 높음 | 전문 콘텐츠, 억양 처리 |
| large-v3 | ~3 GB | 매우 느림 | 최고 | 최상의 정확도 |

모델은 [Hugging Face (Systran)](https://huggingface.co/Systran)에서 다운로드되어 로컬에 저장됩니다. 이미 다운로드된 모델이 있는 폴더를 Katib에 직접 지정할 수도 있습니다.

---

## 설정

| 설정 | 설명 |
|------|------|
| **단축키** | 임의의 키 또는 조합. 기본값: F9 |
| **음성 언어** | 특정 언어를 지정하거나 자동 감지 사용 |
| **정밀도** | `int8` (기본값) · `int8_float32` · `float32` — 속도와 정확도 간 조절 |
| **AI 프롬프트** | 전사 시 Whisper에 전달되는 문맥; 음성 언어별로 별도 저장 |
| **앱 언어** | UI 언어 — 즉시 변경, 재시작 불필요 |

---

## 개인정보 보호

Katib은 완전 폐쇄 환경(에어갭)에서도 사용할 수 있도록 설계되었습니다:

- 런타임 중 외부 연결 없음
- 사용 통계, 오류 보고, 업데이트 확인 없음
- 설정 및 로그는 `%LOCALAPPDATA%\Katib`에 로컬 저장
- 유일한 네트워크 활동은 선택적인 최초 1회 모델 다운로드뿐

---

## 소스에서 빌드

```bash
pip install pyinstaller
pyinstaller Katib.spec
```

출력 경로: `dist/Katib/Katib.exe`

---

## 기여

풀 리퀘스트를 환영합니다. 큰 변경 사항은 먼저 이슈를 열어 방향을 논의해 주세요.

아키텍처 결정 사항은 [`docs/adr/`](docs/adr/)에 문서화되어 있습니다.

---

*Katib (كاتب) — 아랍어로 '서기(書記)'를 뜻합니다.*

**라이선스:** MIT
