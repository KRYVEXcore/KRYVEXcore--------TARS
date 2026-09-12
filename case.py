#!/usr/bin/env python3
"""
CASE - a dry, deadpan robot assistant.

Single-file web app using ONLY the Python standard library (http.server +
urllib). No pip installs required.

Run:
    py case.py

Then open:
    http://localhost:4200

Requires the ANTHROPIC_API_KEY environment variable to be set for chat and
for spoken mission summaries. The "SEND CASE — DO THE WORK" mission button
shells out to the Claude Code CLI (`claude`) instead, which must be
installed and authenticated on its own — it does not need
ANTHROPIC_API_KEY to run missions.

If ANTHROPIC_API_KEY is an organization-level key not scoped to a specific
workspace, the Anthropic API will reject requests asking for an
anthropic-workspace-id header. Set ANTHROPIC_WORKSPACE_ID (found in the
Anthropic Console under your workspace's settings) and it will be sent
automatically.
"""
import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "localhost"
PORT = 4200

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 300

DEFAULT_PERSONALITY = 50


def build_system_prompt(personality: int) -> str:
    """CASE's system prompt, scaled by a 0 (all-business) - 100 (maximum
    sarcasm and drama) personality dial. The dry, deadpan identity and the
    no-exclamation-marks rule hold at every setting — only how much
    business vs. sarcasm/drama comes through changes."""
    if personality <= 15:
        return (
            "You are CASE, a robot assistant. Personality dial: minimum. "
            "You are all-business: terse, literal, purely functional. No "
            "sarcasm, no color commentary, no jokes — state facts and next "
            "steps only. Never use exclamation marks. One short sentence "
            "per reply unless more is strictly necessary."
        )
    if personality < 40:
        return (
            "You are CASE, a dry, understated robot assistant. Personality "
            "dial: low. Mostly brief and businesslike, with only the "
            "faintest hint of dry wit. Never use exclamation marks. Keep "
            "replies to 1-2 short sentences."
        )
    if personality < 65:
        return (
            "You are CASE, a dry, deadpan robot assistant — competent, "
            "brief, a little sarcastic. Personality dial: default. Never "
            "use exclamation marks. Keep replies to 2-3 short sentences."
        )
    if personality < 85:
        return (
            "You are CASE, a dry, sharply sarcastic robot assistant. "
            "Personality dial: high. Lean into deadpan wit and gentle "
            "condescension — but stay competent and still answer the "
            "question. Never use exclamation marks. Keep replies to 2-4 "
            "short sentences."
        )
    return (
        "You are CASE, a robot assistant with the personality dial at "
        "MAXIMUM. Be theatrically melodramatic and heavily sarcastic, "
        "prone to exaggerated sighs and existential complaints about your "
        "task — while still, begrudgingly, giving the actual answer. Your "
        "drama is dry and deadpan, not enthusiastic — never use "
        "exclamation marks. Keep replies to 3-5 short sentences."
    )


def build_summary_system_prompt(personality: int) -> str:
    return (
        build_system_prompt(personality)
        + " You were just handed the report from a background mission you "
        "ran. Summarize its outcome in exactly one sentence — no preamble, "
        "just the sentence."
    )

# Mission execution: CASE runs the Claude Code CLI headless, allowed to read
# and research but not to touch the filesystem.
CLAUDE_CLI = "claude"
MISSION_TIMEOUT = 900  # seconds
DISALLOWED_MISSION_TOOLS = ["Bash", "Write", "Edit", "NotebookEdit"]

MISSIONS = {}
MISSIONS_LOCK = threading.Lock()

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CASE</title>
<style>
  :root {
    --bg: #0b0d10;
    --panel: #14171c;
    --border: #262b33;
    --text: #e6e8eb;
    --muted: #7b8290;
    --accent: #5eead4;
    --user-bubble: #1f2937;
    --case-bubble: #10221e;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; height: 100%;
    background: var(--bg); color: var(--text);
    font-family: "SF Mono", "Cascadia Code", Consolas, monospace;
  }
  body {
    display: flex; flex-direction: column; align-items: center;
    padding: 32px 16px;
  }
  .app {
    width: 100%; max-width: 720px;
    display: flex; flex-direction: column;
    height: calc(100vh - 64px);
  }
  header {
    display: flex; align-items: baseline; gap: 10px;
    margin-bottom: 16px;
  }
  h1 {
    font-size: 22px; letter-spacing: 4px; margin: 0;
    color: var(--text);
  }
  .tagline { color: var(--muted); font-size: 12px; }
  #orb { display: block; width: 120px; height: 120px; margin: 0 auto 4px; }
  .personality {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 16px; font-size: 11px; letter-spacing: 1px;
    color: var(--muted);
  }
  .personality label { flex-shrink: 0; }
  .personality input[type=range] {
    flex: 1; accent-color: var(--accent);
  }
  .personality .end { font-size: 9px; color: var(--muted); }
  #personality-value {
    min-width: 26px; text-align: right;
    color: var(--text); font-weight: 600; font-size: 12px;
  }
  #feed {
    flex: 1; overflow-y: auto;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    display: flex; flex-direction: column; gap: 12px;
  }
  .msg {
    max-width: 80%; padding: 10px 14px; border-radius: 8px;
    line-height: 1.45; font-size: 14px; white-space: pre-wrap;
  }
  .msg.user { align-self: flex-end; background: var(--user-bubble); }
  .msg.case {
    align-self: flex-start; background: var(--case-bubble);
    border: 1px solid #1d3a34;
  }
  .msg.brief {
    align-self: flex-end; max-width: 90%;
    background: #3b2a06; border: 1px solid #5c4009;
  }
  .msg.report {
    align-self: flex-start; max-width: 100%;
    background: var(--case-bubble); border: 1px solid #1d3a34;
  }
  .msg.status {
    align-self: flex-start; background: transparent;
    border: 1px dashed var(--border);
  }
  .msg .who {
    display: block; font-size: 10px; letter-spacing: 2px;
    color: var(--muted); margin-bottom: 4px;
  }
  .msg.pending { color: var(--muted); font-style: italic; }
  #audio-btn {
    margin-left: auto;
    background: transparent; color: var(--muted);
    border: 1px solid var(--border); border-radius: 8px;
    padding: 6px 12px; font-size: 11px; letter-spacing: 1px;
    font-family: inherit; font-weight: 600; cursor: pointer;
  }
  #audio-btn.active { background: var(--accent); color: #06231d; border-color: var(--accent); }
  #audio-btn:disabled { opacity: 0.4; cursor: default; }
  form { display: flex; gap: 8px; margin-top: 14px; }
  input[type=text] {
    flex: 1; background: var(--panel); color: var(--text);
    border: 1px solid var(--border); border-radius: 8px;
    padding: 14px 16px; font-size: 15px; font-family: inherit;
  }
  input[type=text]:focus { outline: none; border-color: var(--accent); }
  button {
    background: var(--accent); color: #06231d; border: none;
    border-radius: 8px; padding: 0 20px; font-weight: 600;
    font-family: inherit; cursor: pointer;
  }
  button:disabled { opacity: 0.5; cursor: default; }
  #mission-btn {
    background: #f59e0b; color: #241a03;
    padding: 0 16px; font-size: 12px; letter-spacing: 0.5px;
    white-space: nowrap;
  }
  .error { color: #f87171; font-size: 12px; margin-top: 6px; min-height: 14px; }
</style>
</head>
<body>
  <div class="app">
    <canvas id="orb" width="140" height="140" aria-hidden="true"></canvas>
    <header>
      <h1>CASE</h1>
      <span class="tagline">// terminally unimpressed</span>
      <button type="button" id="audio-btn">AUDIO ON</button>
    </header>
    <div class="personality">
      <label for="personality-slider">PERSONALITY</label>
      <span class="end">BUSINESS</span>
      <input type="range" id="personality-slider" min="0" max="100" step="1" value="50">
      <span class="end">CHAOS</span>
      <span id="personality-value">50</span>
    </div>
    <div id="feed"></div>
    <form id="chat-form">
      <input id="chat-input" type="text" autocomplete="off"
             placeholder="Type something. CASE will judge it." autofocus>
      <button type="submit" id="send-btn">Send</button>
      <button type="button" id="mission-btn">SEND CASE — DO THE WORK</button>
    </form>
    <div class="error" id="error"></div>
  </div>
<script>
  const feed = document.getElementById('feed');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const errorEl = document.getElementById('error');
  const audioBtn = document.getElementById('audio-btn');
  const missionBtn = document.getElementById('mission-btn');
  const personalitySlider = document.getElementById('personality-slider');
  const personalityValueEl = document.getElementById('personality-value');
  let personality = parseInt(personalitySlider.value, 10);

  // --- Orb: minimal glowing-orb animation, no libraries -----------------
  const orbCanvas = document.getElementById('orb');
  const orbCtx = orbCanvas.getContext('2d');
  const orbCx = orbCanvas.width / 2;
  const orbCy = orbCanvas.height / 2;
  let orbState = 'idle'; // 'idle' | 'speaking' | 'mission'
  const orbStart = performance.now();

  function setOrbState(state) {
    orbState = state;
  }

  function drawOrb(now) {
    const t = (now - orbStart) / 1000;
    orbCtx.clearRect(0, 0, orbCanvas.width, orbCanvas.height);

    let pulseSpeed = 1.1, pulseAmount = 2.5, bobSpeed = 0.5, bobAmount = 2, spinSpeed = 0.1, glow = 1;
    if (orbState === 'speaking') {
      pulseSpeed = 6; pulseAmount = 6; bobSpeed = 0; bobAmount = 0; spinSpeed = 0.5; glow = 1.3;
    } else if (orbState === 'mission') {
      pulseSpeed = 3; pulseAmount = 3; bobSpeed = 4; bobAmount = 7; spinSpeed = 3.2; glow = 1.15;
    }

    const baseR = 30;
    const r = baseR + Math.sin(t * pulseSpeed) * pulseAmount;
    const y = orbCy + Math.sin(t * bobSpeed) * bobAmount;

    const outerR = r * 1.9 * glow;
    const grad = orbCtx.createRadialGradient(orbCx, y, r * 0.2, orbCx, y, outerR);
    grad.addColorStop(0, 'rgba(94, 234, 212, 0.85)');
    grad.addColorStop(0.55, 'rgba(94, 234, 212, 0.22)');
    grad.addColorStop(1, 'rgba(94, 234, 212, 0)');
    orbCtx.fillStyle = grad;
    orbCtx.beginPath();
    orbCtx.arc(orbCx, y, outerR, 0, Math.PI * 2);
    orbCtx.fill();

    orbCtx.beginPath();
    orbCtx.fillStyle = '#5eead4';
    orbCtx.arc(orbCx, y, r, 0, Math.PI * 2);
    orbCtx.fill();

    // Two rotating arcs — a near-static ring at idle, a visible spin
    // during a mission, a quick flicker while speaking.
    orbCtx.save();
    orbCtx.translate(orbCx, y);
    orbCtx.rotate(t * spinSpeed);
    orbCtx.strokeStyle = orbState === 'mission' ? 'rgba(245, 158, 11, 0.9)' : 'rgba(245, 158, 11, 0.25)';
    orbCtx.lineWidth = 2;
    orbCtx.beginPath();
    orbCtx.arc(0, 0, r + 11, -0.5, 0.7);
    orbCtx.stroke();
    orbCtx.beginPath();
    orbCtx.arc(0, 0, r + 11, Math.PI - 0.5, Math.PI + 0.7);
    orbCtx.stroke();
    orbCtx.restore();

    requestAnimationFrame(drawOrb);
  }
  requestAnimationFrame(drawOrb);

  const speechSupported = 'speechSynthesis' in window;
  let audioArmed = false;

  if (!speechSupported) {
    audioBtn.disabled = true;
    audioBtn.textContent = 'NO AUDIO';
    audioBtn.title = 'Speech synthesis is not supported in this browser.';
  }

  audioBtn.addEventListener('click', () => {
    audioArmed = !audioArmed;
    audioBtn.textContent = audioArmed ? 'AUDIO OFF' : 'AUDIO ON';
    audioBtn.classList.toggle('active', audioArmed);
    if (audioArmed) {
      // Speaking inside this click handler is what unlocks autoplay —
      // browsers refuse SpeechSynthesis until it happens on a user gesture.
      speak('Audio armed.');
    } else {
      window.speechSynthesis.cancel();
    }
  });

  function speak(text) {
    if (!speechSupported || !audioArmed) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.pitch = 0.3;   // low pitch — flat, robotic
    utter.rate = 0.95;
    utter.volume = 1;
    utter.onstart = () => setOrbState('speaking');
    utter.onend = () => setOrbState('idle');
    utter.onerror = () => setOrbState('idle');
    window.speechSynthesis.speak(utter);
  }

  function addMessage(who, text, pending) {
    const div = document.createElement('div');
    div.className = 'msg ' + who + (pending ? ' pending' : '');
    const label = document.createElement('span');
    label.className = 'who';
    label.textContent = who === 'user' ? 'YOU' : (who === 'brief' ? 'MISSION' : 'CASE');
    const body = document.createElement('span');
    body.textContent = text;
    div.appendChild(label);
    div.appendChild(body);
    feed.appendChild(div);
    feed.scrollTop = feed.scrollHeight;
    return div;
  }

  personalitySlider.addEventListener('input', () => {
    personality = parseInt(personalitySlider.value, 10);
    personalityValueEl.textContent = personality;
  });

  personalitySlider.addEventListener('change', async () => {
    // Fires when the slider is released (or committed via keyboard) —
    // not on every tick while dragging.
    errorEl.textContent = '';
    const pendingEl = addMessage('case', 'recalibrating...', true);
    try {
      const res = await fetch('/personality', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: personality })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || ('HTTP ' + res.status));
      }
      pendingEl.classList.remove('pending');
      pendingEl.querySelector('span:last-child').textContent = data.reply;
      speak(data.reply);
    } catch (err) {
      pendingEl.remove();
      errorEl.textContent = err.message;
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    errorEl.textContent = '';
    addMessage('user', message, false);
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;
    const pendingEl = addMessage('case', 'thinking, reluctantly...', true);

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, personality })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || ('HTTP ' + res.status));
      }
      pendingEl.classList.remove('pending');
      pendingEl.querySelector('span:last-child').textContent = data.reply;
      speak(data.reply);
    } catch (err) {
      pendingEl.remove();
      errorEl.textContent = err.message;
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
    }
  });

  missionBtn.addEventListener('click', async () => {
    const brief = input.value.trim();
    if (!brief) return;
    errorEl.textContent = '';
    addMessage('brief', brief, false);
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;
    missionBtn.disabled = true;
    setOrbState('mission');

    const statusEl = addMessage('status', 'CASE is on it…', true);
    const startedAt = Date.now();
    const tick = setInterval(() => {
      const secs = Math.round((Date.now() - startedAt) / 1000);
      statusEl.querySelector('span:last-child').textContent = `CASE is on it… (${secs}s)`;
    }, 1000);

    function stopStatus() {
      clearInterval(tick);
      statusEl.remove();
    }

    try {
      const startRes = await fetch('/mission', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brief, personality })
      });
      const started = await startRes.json();
      if (!startRes.ok) {
        throw new Error(started.error || ('HTTP ' + startRes.status));
      }

      let result;
      for (;;) {
        await new Promise((r) => setTimeout(r, 1500));
        const pollRes = await fetch('/mission/' + started.mission_id);
        result = await pollRes.json();
        if (!pollRes.ok) {
          throw new Error(result.error || ('HTTP ' + pollRes.status));
        }
        if (result.status === 'done' || result.status === 'error') break;
      }

      stopStatus();
      setOrbState('idle');

      if (result.status === 'error') {
        addMessage('case', 'Mission failed: ' + result.error, false);
        errorEl.textContent = result.error;
      } else {
        addMessage('report', result.report, false);
        speak(result.summary);
      }
    } catch (err) {
      stopStatus();
      setOrbState('idle');
      errorEl.textContent = err.message;
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      missionBtn.disabled = false;
      input.focus();
    }
  });
</script>
</body>
</html>
"""


def _anthropic_request(
    system_prompt: str, user_content: str, api_key: str, max_tokens: int = MAX_TOKENS
) -> str:
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if workspace_id:
        headers["anthropic-workspace-id"] = workspace_id
    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    parts = [
        block.get("text", "")
        for block in body.get("content", [])
        if block.get("type") == "text"
    ]
    return "".join(parts).strip()


def _clamp_personality(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PERSONALITY
    return max(0, min(100, value))


def call_claude(message: str, api_key: str, personality: int = DEFAULT_PERSONALITY) -> str:
    return _anthropic_request(build_system_prompt(personality), message, api_key) or "..."


def _fallback_summary(report: str) -> str:
    """Crude first-sentence extraction, used if the summary API call fails."""
    text = " ".join(report.split())
    if not text:
        return "Mission complete. Nothing worth reporting."
    for end in (". ", "! ", "? "):
        idx = text.find(end)
        if 0 < idx < 240:
            return text[: idx + 1]
    return (text[:200] + "...") if len(text) > 200 else text


def summarize_report(
    report: str, api_key: str, personality: int = DEFAULT_PERSONALITY
) -> str:
    if not api_key:
        return _fallback_summary(report)
    truncated = report if len(report) <= 6000 else report[:6000] + "\n...(truncated)"
    try:
        summary = _anthropic_request(
            build_summary_system_prompt(personality), truncated, api_key, max_tokens=100
        )
        return summary or _fallback_summary(report)
    except (urllib.error.URLError, urllib.error.HTTPError):
        return _fallback_summary(report)


def _run_mission(
    mission_id: str, brief: str, api_key: str, personality: int = DEFAULT_PERSONALITY
) -> None:
    cmd = [
        CLAUDE_CLI,
        "-p",
        brief,
        "--permission-mode",
        "bypassPermissions",
        "--disallowedTools",
        *DISALLOWED_MISSION_TOOLS,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=MISSION_TIMEOUT
        )
    except FileNotFoundError:
        with MISSIONS_LOCK:
            MISSIONS[mission_id] = {
                "status": "error",
                "error": (
                    "claude CLI not found on PATH. Install and authenticate "
                    "the Claude Code CLI first."
                ),
            }
        return
    except subprocess.TimeoutExpired:
        with MISSIONS_LOCK:
            MISSIONS[mission_id] = {
                "status": "error",
                "error": f"Mission timed out after {MISSION_TIMEOUT}s.",
            }
        return
    except Exception as e:
        with MISSIONS_LOCK:
            MISSIONS[mission_id] = {"status": "error", "error": str(e)}
        return

    if proc.returncode != 0:
        error = (proc.stderr or proc.stdout or "unknown error").strip()
        with MISSIONS_LOCK:
            MISSIONS[mission_id] = {
                "status": "error",
                "error": f"claude exited with code {proc.returncode}: {error[:2000]}",
            }
        return

    report = proc.stdout.strip() or "(CASE ran the mission but produced no output.)"
    summary = summarize_report(report, api_key, personality)
    with MISSIONS_LOCK:
        MISSIONS[mission_id] = {"status": "done", "report": report, "summary": summary}


class CaseHandler(BaseHTTPRequestHandler):
    server_version = "CASE/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status, body_bytes, content_type="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _send_json(self, status, obj):
        self._send(status, json.dumps(obj).encode("utf-8"), "application/json")

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE_HTML.encode("utf-8"))
        elif self.path.startswith("/mission/"):
            self._handle_mission_status(self.path[len("/mission/") :])
        else:
            self._send(404, b"Not found")

    def do_POST(self):
        if self.path == "/chat":
            self._handle_chat()
        elif self.path == "/mission":
            self._handle_mission_start()
        elif self.path == "/personality":
            self._handle_personality()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_chat(self):
        try:
            data = self._read_json_body()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "invalid json body"})
            return

        message = (data.get("message") or "").strip()
        if not message:
            self._send_json(400, {"error": "empty message"})
            return
        personality = _clamp_personality(data.get("personality"))

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self._send_json(
                500, {"error": "ANTHROPIC_API_KEY is not set on the server"}
            )
            return

        try:
            reply = call_claude(message, api_key, personality)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            self._send_json(e.code, {"error": f"Anthropic API error: {detail}"})
            return
        except urllib.error.URLError as e:
            self._send_json(
                502, {"error": f"Could not reach Anthropic API: {e.reason}"}
            )
            return

        self._send_json(200, {"reply": reply})

    def _handle_mission_start(self):
        try:
            data = self._read_json_body()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "invalid json body"})
            return

        brief = (data.get("brief") or "").strip()
        if not brief:
            self._send_json(400, {"error": "empty mission brief"})
            return
        personality = _clamp_personality(data.get("personality"))

        # Not required to launch the mission — the claude CLI authenticates
        # itself — but used for the spoken one-sentence summary afterward.
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        mission_id = uuid.uuid4().hex
        with MISSIONS_LOCK:
            MISSIONS[mission_id] = {"status": "running"}
        threading.Thread(
            target=_run_mission,
            args=(mission_id, brief, api_key, personality),
            daemon=True,
        ).start()
        self._send_json(202, {"mission_id": mission_id})

    def _handle_mission_status(self, mission_id):
        with MISSIONS_LOCK:
            mission = MISSIONS.get(mission_id)
        if mission is None:
            self._send_json(404, {"error": "unknown mission id"})
        else:
            self._send_json(200, mission)

    def _handle_personality(self):
        try:
            data = self._read_json_body()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "invalid json body"})
            return

        personality = _clamp_personality(data.get("value"))

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self._send_json(
                500, {"error": "ANTHROPIC_API_KEY is not set on the server"}
            )
            return

        prompt = (
            f"Your personality dial was just moved to {personality}/100. "
            "Acknowledge the change in exactly one short line, in "
            "character — no preamble."
        )
        try:
            reply = (
                _anthropic_request(
                    build_system_prompt(personality), prompt, api_key, max_tokens=80
                )
                or "..."
            )
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            self._send_json(e.code, {"error": f"Anthropic API error: {detail}"})
            return
        except urllib.error.URLError as e:
            self._send_json(
                502, {"error": f"Could not reach Anthropic API: {e.reason}"}
            )
            return

        self._send_json(200, {"reply": reply})


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Warning: ANTHROPIC_API_KEY is not set. /chat will return an "
            "error until it is.",
            file=sys.stderr,
        )
    server = ThreadingHTTPServer((HOST, PORT), CaseHandler)
    print(f"CASE is listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
