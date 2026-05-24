[English](README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [日本語](README.ja.md) · [中文](README.zh.md) · [한국어](README.ko.md) · [العربية](README.ar.md)

# Katib

**Windows 离线语音听写工具。按住按键、开口说话、松开按键 — 文字即刻出现在光标处。**

无需云端。无需订阅。数据永不离开本机。

---

<p align="center">
  <img src="docs/demo.gif" alt="Hold F9, speak, release — text appears" width="800">
</p>

---

## 使用方式

1. 点击任意文本框 — 浏览器、Word、IDE、聊天窗口，Windows 上的任何地方均可
2. 按住热键（默认 **F9**），说话，松开
3. 语音由 [Whisper](https://github.com/openai/whisper) 在本地转录，并输入到光标位置

模型首次下载后，无需任何网络连接。

---

## 功能特性

- **完全离线** — Whisper 完全在 CPU 上运行，无需 API 密钥，无需注册账号
- **随处可用** — 支持 Windows 任意应用程序中的可聚焦文本框
- **按键说话** — 按住录音，松开转录，不会意外触发
- **五种模型大小** — 从 150 MB 到 3 GB；根据硬件在速度与精度之间灵活选择
- **18 种转录语言** — 阿拉伯语、中文、英语、法语、德语、希腊语、印地语、印度尼西亚语、意大利语、日语、韩语、波斯语、葡萄牙语、俄语、西班牙语、土耳其语、乌尔都语，以及自动检测
- **11 种界面语言** — English、Türkçe、Deutsch、Español、Français、Português、Русский、日本語、中文、한국어、العربية — 完整支持 RTL 从右到左布局
- **按语言配置 AI 提示词** — 为每种语音语言单独设置上下文，切换时自动加载
- **零遥测** — 无数据分析、无崩溃上报、无更新检查

---

## 安装方式

### 方式 A — 预编译二进制文件（推荐）

从 [Releases](../../releases) 页面下载最新版本，解压后运行 `Katib.exe`。

> 由于二进制文件未签名，**Windows SmartScreen** 可能显示安全警告。点击**更多信息 → 仍要运行**即可。

### 方式 B — 从源码运行

需要 Python 3.10 及以上版本

```bash
git clone https://github.com/zntkr/katib.git
cd katib
pip install -r requirements.txt
python main.py
```

---

## 模型

| 模型 | 大小 | 速度 | 精度 | 说明 |
|------|------|------|------|------|
| tiny | ~150 MB | 极快 | 低 | 适合低端或老旧硬件 |
| base | ~300 MB | 较快 | 一般 | |
| **small** | **~500 MB** | **均衡** | **良好** | **推荐入门选择** |
| medium | ~1.5 GB | 较慢 | 高 | 适合专业术语、口音内容 |
| large-v3 | ~3 GB | 极慢 | 最高 | 最佳转录精度 |

模型从 [Hugging Face (Systran)](https://huggingface.co/Systran) 下载并存储在本地。您也可以将 Katib 指向已下载模型所在的本地文件夹。

---

## 设置

| 设置项 | 说明 |
|--------|------|
| **热键** | 任意按键或组合键。默认：F9 |
| **语音语言** | 指定特定语言，或使用自动检测 |
| **精度** | `int8`（默认）· `int8_float32` · `float32` — 速度与精度的权衡 |
| **AI 提示词** | 每次转录时传递给 Whisper 的上下文；按语音语言分别保存 |
| **界面语言** | UI 显示语言 — 即时生效，无需重启 |

---

## 隐私说明

Katib 设计上支持完全隔离网络的环境：

- 运行时无任何对外连接
- 不收集使用统计、不上报错误、不检查更新
- 设置与日志存储在本地的 `%LOCALAPPDATA%\Katib`
- 唯一的网络活动是可选的首次模型下载

---

## 从源码构建

```bash
pip install pyinstaller
pyinstaller Katib.spec
```

输出文件：`dist/Katib/Katib.exe`

---

## 贡献

欢迎提交 Pull Request。如需进行较大改动，请先提 Issue 讨论方案。

架构决策记录见 [`docs/adr/`](docs/adr/)。

---

*Katib（كاتب）— 阿拉伯语，意为"书记官"。*

**许可证：** MIT
