# CASE

CASE is a dark-mode, personality-driven robot assistant, built as a single
Python file with zero dependencies. Chat with it, tune its attitude live
with a PERSONALITY slider, hear it talk, and hand it real research/coding
missions that it runs headless in the background via the Claude Code CLI.

## Features

- **Chat** — type a message, CASE (Claude Haiku) replies in 2-3 dry,
  deadpan sentences.
- **Voice** — every reply is spoken aloud with the browser's built-in
  SpeechSynthesis API (low pitch, robotic). Toggle with the AUDIO ON/OFF
  button.
- **PERSONALITY slider** — 0 (all-business, terse) to 100 (maximally
  sarcastic and dramatic). Updates CASE's system prompt live, and CASE
  speaks a one-line confirmation when you let go of the slider.
- **Missions** — "SEND CASE — DO THE WORK" hands your typed brief to the
  `claude` CLI headless, in the background, with
  `--permission-mode bypassPermissions --disallowedTools Bash Write Edit
  NotebookEdit` — so it can research and read, but can't touch your files.
  The full report lands in the feed, plus a spoken one-sentence summary.
- **Orb** — a small canvas animation above the header that pulses while
  CASE is speaking and spins/bobs faster while a mission is running.
- **Zero dependencies** — pure `http.server` + `urllib` from the Python
  standard library. No `pip install`, ever.

## Requirements

- Python 3 (`py` on Windows, `python3` on macOS/Linux)
- An Anthropic API key
- If your key is org-level rather than workspace-scoped, an
  `ANTHROPIC_WORKSPACE_ID` too (found in the Anthropic Console under your
  workspace's settings)
- Optional, for missions only: the [Claude Code CLI](https://claude.com/claude-code)
  (`claude`) installed and authenticated on `PATH`. Chat and the
  personality slider work without it.

## Run it — one command

```bash
ANTHROPIC_API_KEY="sk-ant-your-key-here" py case.py
```

Windows PowerShell:

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"; py case.py
```

Or set the key once, persistently, and just run `py case.py` from then on:

```bash
setx ANTHROPIC_API_KEY "sk-ant-your-key-here"   # Windows, one-time
export ANTHROPIC_API_KEY="sk-ant-your-key-here" # macOS/Linux, per shell
```

If your key needs a workspace scope, set `ANTHROPIC_WORKSPACE_ID` the same
way.

Then open:

```
http://localhost:4200
```

## Files

- `case.py` — the entire app: HTTP server, HTML/CSS/JS page, and all
  chat/mission/personality logic, in one file.
