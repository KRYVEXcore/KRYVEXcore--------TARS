[TARS-README_1.md](https://github.com/user-attachments/files/32146871/TARS-README_1.md)
<div align="center">

# 🤖 C.A.S.E.
### Cold, Analytical, Sarcastic, Efficient

**A dark-mode, personality-driven AI assistant — one Python file, zero dependencies.**

![Python](https://img.shields.io/badge/python-3-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/dependencies-zero-2ecc71?style=for-the-badge)
![Model](https://img.shields.io/badge/model-Claude%20Haiku-D97757?style=for-the-badge)
![License](https://img.shields.io/badge/license-GPL--2.0-blue?style=for-the-badge)

*Named for the robots of Interstellar — TARS and CASE were built with adjustable honesty and humor settings. This one keeps that idea and puts it on a slider.*

[Quick Start](#-quick-start) · [Features](#-features) · [Personality Engine](#-personality-engine) · [Missions](#-missions) · [API](#-api-reference) · [License](#-license)

</div>

<br/>

## 👋 What Is This?

**CASE** is a single-file, dependency-free AI assistant that runs locally in your browser. No frameworks, no build step, no package install — `python case.py` and it's live at `localhost:4200`.

Under the hood it talks to **Claude Haiku** for conversation, keeps its tone tuned by a **personality slider** (all-business at 0, theatrically dramatic at 100), and can hand off longer research or coding tasks as **background missions** that run through the Claude Code CLI in a read-only sandbox.

It's built to be *read* in one sitting — the entire server, UI, and logic live in one `case.py` file using nothing but the Python standard library.

<br/>

## ✨ Features

| Feature | Description |
|---|---|
| **Chat** | Conversational responses from Claude Haiku, kept short — 2–3 dry, deadpan sentences by default |
| **Personality Slider** | A single 0–100 dial that rewrites CASE's system prompt in real time, from terse professional to full melodrama |
| **Text-to-Speech** | Responses are read aloud via the browser's native `SpeechSynthesis` API — no audio backend required |
| **Missions** | Hand off a research or coding brief; it runs in the background via the Claude Code CLI and reports back when done |
| **Animated Orb** | A single visual indicator — pulses while CASE is speaking, spins faster while a mission is active |
| **Zero Dependencies** | Just `http.server` and `urllib` from the standard library. No `pip install`, no `node_modules` |

<br/>

## 🚀 Quick Start

**Requirements:** Python 3, an [Anthropic API key](https://console.anthropic.com/settings/keys), and (optionally) the [Claude Code CLI](https://claude.com/claude-code) for missions.

```bash
git clone https://github.com/KRYVEXcore/KRYVEXcore--------TARS.git
cd KRYVEXcore--------TARS

export ANTHROPIC_API_KEY="sk-ant-..."
python case.py
```

Then open **http://localhost:4200** — that's the whole install.

> Using an org-scoped key? Set `ANTHROPIC_WORKSPACE_ID` as well and it's included automatically on every request.

<br/>

## 🎚️ Personality Engine

The slider isn't cosmetic — it rewrites CASE's system prompt live, the same way TARS's humor setting worked in the film. Every band bans exclamation marks; only tone and length change.

| Range | Demeanor |
|---|---|
| **0–15** | All-business. Terse, purely functional, no embellishment |
| **16–39** | Mostly brief, with the faintest hint of dry wit |
| **40–64** | Default — deadpan delivery with light sarcasm *(this is the resting setting)* |
| **65–84** | Sharp sarcasm, gentle condescension |
| **85–100** | Theatrically melodramatic, prone to existential complaints |

<br/>

## 🛰️ Missions

Missions let CASE act on longer requests without blocking the chat. A mission brief is handed to the Claude Code CLI as a background subprocess:

```
claude -p "<brief>" --permission-mode bypassPermissions \
  --disallowedTools Bash Write Edit NotebookEdit
```

- **Read-only by design** — `Bash`, `Write`, `Edit`, and `NotebookEdit` are explicitly disallowed, so a mission can research and reason but never touch your filesystem.
- **900-second timeout** per mission.
- The subprocess's output becomes the mission report, which CASE then summarizes back into its own voice.
- The UI polls mission status and spins the orb faster while one is running.

```
You ──> POST /mission {brief} ──> background thread ──> claude CLI (sandboxed, read-only)
                                          │
                                          ▼
                        UI polls GET /mission/{id} ──> status / report / summary
```

<br/>

## 🔌 API Reference

CASE serves a small, self-contained set of routes — no external API surface beyond Anthropic itself.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/` or `/index.html` | Serves the web UI |
| `POST` | `/chat` | `{ message, personality }` → Claude's reply |
| `POST` | `/mission` | `{ brief, personality }` → starts a background mission, returns `mission_id` |
| `GET` | `/mission/{id}` | Polls a mission's `status`, `report`, and `summary` |
| `POST` | `/personality` | `{ value }` → returns a calibration acknowledgment for the new setting |

<br/>

## 🏗️ Architecture

Everything — server, UI, and logic — lives in `case.py`:

- **`CaseHandler`** — the HTTP request dispatcher (built on `http.server.ThreadingHTTPServer`)
- **`build_system_prompt(personality)`** — turns the slider value into a system prompt
- **`call_claude()`** — makes the Anthropic API request for chat
- **`_run_mission()`** — spawns and supervises the sandboxed Claude Code CLI subprocess
- **`PAGE_HTML`** — the entire front end: markup, styling, and JS (orb animation, TTS, mission polling) in one string

No templates, no static file server, no build pipeline — the process serves itself.

<br/>

## 🔒 Scope & Safety

- Missions run with write tools explicitly disabled — CASE can look things up and reason about code, but a mission cannot modify files on your machine.
- Your Anthropic API key stays local; it's read from the environment and only ever sent to Anthropic's API.
- No telemetry, no external services beyond the Anthropic API and (for missions) the Claude Code CLI you already have installed.

<br/>

## 📜 License

Licensed under the **GNU General Public License v2.0 (GPL-2.0)**. See [`LICENSE`](./LICENSE) for the full text.

<br/>

## 🙏 Acknowledgements

- **TARS & CASE**, *Interstellar* (2014) — for the idea that an assistant's honesty and humor should be a dial, not a fixed personality.
- **Anthropic** — Claude Haiku for conversation, Claude Code for mission execution.

<div align="center">

*Honesty setting: adjustable. Humor setting: your call.*

</div>
