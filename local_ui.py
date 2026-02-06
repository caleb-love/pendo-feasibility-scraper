"""
Local web UI server for the Pendo Feasibility Scraper.

Serves a self-contained Apple II CRT-themed interface in the browser.
No Redis, no Google OAuth, no build step -- just run and go.

Usage (typically called from main()):
    from local_ui import launch
    launch()
"""

import json
import threading
import time
import uuid
import webbrowser
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from pendo_feasibility_scraper import run_scan, ScrapeConfig


# ---------------------------------------------------------------------------
# Scan state management
# ---------------------------------------------------------------------------

class ScanState:
    """Thread-safe container for a running scan's state."""

    def __init__(self, scan_id: str, config: dict):
        self.id = scan_id
        self.config = config
        self.status = 'running'      # running | waiting_for_login | done | error
        self.progress: list[str] = []
        self.report_text = ''
        self.report_json: dict = {}
        self.error = ''
        self.login_event = threading.Event()
        self._lock = threading.Lock()

    def add_progress(self, msg: str) -> None:
        """Append a progress line (thread-safe)."""
        with self._lock:
            self.progress.append(msg)
            if msg == 'WAITING FOR LOGIN...':
                self.status = 'waiting_for_login'

    def to_dict(self) -> dict:
        """Snapshot for the API response."""
        with self._lock:
            return {
                'id': self.id,
                'status': self.status,
                'progress': list(self.progress),
                'report_text': self.report_text,
                'report_json': self.report_json,
                'error': self.error,
            }


# Active scans keyed by ID. In local mode there's typically only one.
_scans: dict[str, ScanState] = {}


def _run_scan_thread(state: ScanState) -> None:
    """Execute a scan in a background thread, updating state as it goes."""
    try:
        cfg = state.config
        config = ScrapeConfig(
            max_links=int(cfg.get('max_links', 20)),
            max_pages=int(cfg.get('max_pages', 12)),
            headless=bool(cfg.get('headless', True)),
            login_mode=cfg.get('login_mode', 'manual'),
            login_url=cfg.get('login_url', ''),
            username_selector=cfg.get('username_selector', ''),
            password_selector=cfg.get('password_selector', ''),
            submit_selector=cfg.get('submit_selector', ''),
            username=cfg.get('username', ''),
            password=cfg.get('password', ''),
            storage_state_path=cfg.get('storage_state_path', ''),
            dismiss_popups=bool(cfg.get('dismiss_popups', True)),
            scroll_pages=bool(cfg.get('scroll_pages', True)),
        )

        result = run_scan(
            start_url=cfg['target_url'],
            config=config,
            progress_callback=state.add_progress,
            login_event=state.login_event if config.login_mode == 'manual' else None,
        )

        state.report_text = result.report_text
        state.report_json = result.report_json
        state.status = 'done'

    except Exception as exc:
        state.error = str(exc)
        state.status = 'error'
        state.add_progress(f'ERROR: {exc}')


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title='Pendo Feasibility Scraper – Local UI')


class ScanRequest(BaseModel):
    """Payload for starting a scan."""
    target_url: str
    config: dict = {}


@app.get('/', response_class=HTMLResponse)
def index():
    """Serve the self-contained Apple II UI."""
    return HTML_PAGE


@app.post('/api/scan')
def start_scan(req: ScanRequest):
    """Start a scan in a background thread."""
    scan_id = str(uuid.uuid4())[:8]
    merged = {**req.config, 'target_url': req.target_url}
    state = ScanState(scan_id, merged)
    _scans[scan_id] = state
    thread = threading.Thread(target=_run_scan_thread, args=(state,), daemon=True)
    thread.start()
    return {'id': scan_id, 'status': 'running'}


@app.get('/api/scan/{scan_id}')
def get_scan(scan_id: str):
    """Poll scan status and progress."""
    state = _scans.get(scan_id)
    if not state:
        return JSONResponse({'error': 'Scan not found'}, status_code=404)
    return state.to_dict()


@app.post('/api/scan/{scan_id}/continue')
def continue_scan(scan_id: str):
    """Signal the scan to continue past the manual login wait."""
    state = _scans.get(scan_id)
    if not state:
        return JSONResponse({'error': 'Scan not found'}, status_code=404)
    state.login_event.set()
    state.status = 'running'
    state.add_progress('LOGIN CONFIRMED - CONTINUING SCAN')
    return {'ok': True}


# ---------------------------------------------------------------------------
# Launch helper
# ---------------------------------------------------------------------------

def launch(port: int = 8080) -> None:
    """Start the local server and auto-open the browser."""
    url = f'http://localhost:{port}'
    print(f'\n  PENDO FEASIBILITY SCRAPER //e')
    print(f'  Local UI: {url}')
    print(f'  Press Ctrl+C to stop.\n')
    # Open browser after a short delay so the server is ready.
    threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')


# ---------------------------------------------------------------------------
# Embedded HTML – self-contained Apple ][ CRT interface
# ---------------------------------------------------------------------------

HTML_PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PENDO FEASIBILITY SCRAPER //e</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --green:#33ff33;--green-dim:#1a9a1a;--green-glow:#33ff3366;
  --amber:#ffb000;--bg:#0a0a0a;--bezel:#3a3632;--bezel-light:#4a4642;
  --font:'Press Start 2P',monospace;--fs:10px;--fs-sm:8px;--fs-lg:12px;
}
html{font-size:16px}
body{margin:0;font-family:var(--font);font-size:var(--fs);background:#1a1816;
  color:var(--green);min-height:100vh;display:flex;align-items:center;
  justify-content:center;overflow-x:hidden}

/* Monitor bezel */
.monitor{background:linear-gradient(145deg,var(--bezel-light),var(--bezel));
  border-radius:24px;padding:28px 32px 40px;
  box-shadow:0 20px 60px rgba(0,0,0,.8),inset 0 1px 0 rgba(255,255,255,.08);
  max-width:820px;width:95vw;margin:24px auto;position:relative}
.monitor::after{content:'PENDO //e';position:absolute;bottom:10px;left:50%;
  transform:translateX(-50%);font-family:var(--font);font-size:8px;
  color:#666;letter-spacing:3px}

/* CRT screen */
.screen{background:var(--bg);border-radius:12px;border:3px solid #111;
  padding:24px 28px;min-height:520px;position:relative;overflow:hidden;
  box-shadow:inset 0 0 80px rgba(51,255,51,.04),inset 0 0 8px rgba(0,0,0,.6)}
.screen::before{content:'';position:absolute;inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,
  rgba(0,0,0,.06) 2px,rgba(0,0,0,.06) 4px);pointer-events:none;z-index:10}
.screen::after{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse at center,transparent 60%,rgba(0,0,0,.35) 100%);
  pointer-events:none;z-index:11}

@keyframes flicker{0%{opacity:.97}5%{opacity:1}50%{opacity:1}80%{opacity:.97}100%{opacity:1}}
.sc{position:relative;z-index:5;animation:flicker 4s infinite}

/* Typography */
h2{font-size:var(--fs);color:var(--green);text-shadow:0 0 6px var(--green-glow);
  margin-bottom:12px;text-transform:uppercase}
a{color:var(--green);text-decoration:none}

.ascii{white-space:pre;font-size:7px;line-height:1.2;color:var(--green);
  text-shadow:0 0 6px var(--green-glow);margin-bottom:8px;text-align:center;overflow:hidden}
.divider{border:none;border-top:1px solid var(--green-dim);margin:14px 0;opacity:.4}

/* Prompt + cursor */
.prompt{margin-top:12px;color:var(--green-dim);font-size:var(--fs-sm)}
.cursor{display:inline-block;width:8px;height:12px;background:var(--green);
  animation:blink 1s step-end infinite;vertical-align:middle;margin-left:2px}
@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}

/* Form */
label{display:block;margin:8px 0 3px;font-size:var(--fs-sm);color:var(--green-dim);
  text-transform:uppercase;letter-spacing:1px}
input[type="text"],input[type="number"],input[type="password"],select{
  display:block;width:100%;padding:7px 9px;margin-top:3px;font-family:var(--font);
  font-size:var(--fs-sm);color:var(--green);background:rgba(51,255,51,.04);
  border:1px solid var(--green-dim);border-radius:0;outline:none;caret-color:var(--green)}
input:focus,select:focus{border-color:var(--green);box-shadow:0 0 8px var(--green-glow)}
select{appearance:none;-webkit-appearance:none;cursor:pointer}
select option{background:#111;color:var(--green)}

.chk{display:flex;align-items:center;gap:8px;margin:8px 0}
.chk input[type="checkbox"]{appearance:none;-webkit-appearance:none;width:14px;height:14px;
  border:1px solid var(--green-dim);background:transparent;cursor:pointer;position:relative}
.chk input[type="checkbox"]:checked{background:var(--green);box-shadow:0 0 6px var(--green-glow)}
.chk input[type="checkbox"]:checked::after{content:'';position:absolute;inset:2px;background:var(--bg)}
.chk label{margin:0;cursor:pointer}

/* Buttons */
.btn{display:inline-block;padding:10px 18px;font-family:var(--font);font-size:var(--fs-sm);
  color:var(--bg);background:var(--green);border:none;cursor:pointer;text-transform:uppercase;
  letter-spacing:2px;text-decoration:none;margin-top:12px}
.btn:hover{background:#55ff55;box-shadow:0 0 16px var(--green-glow)}
.btn:active{background:var(--green-dim)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-outline{background:transparent;color:var(--green);border:1px solid var(--green-dim)}
.btn-outline:hover{background:rgba(51,255,51,.1);border-color:var(--green)}
.btn-sm{padding:6px 12px;font-size:7px;margin-top:0}
.btn-amber{background:var(--amber);color:var(--bg)}
.btn-amber:hover{background:#ffc940}

/* Sections */
.section{border:1px solid rgba(51,255,51,.15);padding:14px;margin:14px 0}
.hidden{display:none!important}

/* Progress output */
.output{font-size:var(--fs-sm);line-height:2;color:var(--green);white-space:pre-wrap;
  max-height:320px;overflow-y:auto;padding:4px 0}
.output .line{opacity:0;animation:typeIn .08s ease-in forwards}
@keyframes typeIn{from{opacity:0}to{opacity:1}}

/* Report */
.report{font-size:var(--fs-sm);line-height:1.8;color:var(--green);
  white-space:pre-wrap;word-break:break-word;max-height:500px;overflow-y:auto}

/* Error */
.err{color:#ff4444;font-size:var(--fs-sm);margin:8px 0;text-shadow:0 0 6px rgba(255,68,68,.4)}

/* Scrollbar */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--green-dim)}
::-webkit-scrollbar-thumb:hover{background:var(--green)}

/* Responsive */
@media(max-width:640px){
  .monitor{border-radius:12px;padding:14px 10px 28px;margin:8px}
  .screen{padding:14px 12px;min-height:400px}
  .ascii{font-size:4.5px}
  :root{--fs:8px;--fs-sm:7px;--fs-lg:10px}
}
</style>
</head>
<body>
<div class="monitor">
<div class="screen">
<div class="sc" id="app">

<pre class="ascii">
 ____  _____ _   _ ____   ___
|  _ \| ____| \ | |  _ \ / _ \
| |_) |  _| |  \| | | | | | | |
|  __/| |___| |\  | |_| | |_| |
|_|   |_____|_| \_|____/ \___/
  FEASIBILITY  SCRAPER  //e
</pre>
<hr class="divider">

<!-- ==================== FORM SECTION ==================== -->
<div id="form-section">
  <h2>] NEW SCAN</h2>
  <form id="scan-form">
    <label>TARGET URL</label>
    <input id="f-url" type="text" placeholder="HTTPS://APP.EXAMPLE.COM" required autofocus>

    <label>MAX PAGES</label>
    <input id="f-pages" type="number" value="12" min="1" max="50">

    <div class="chk">
      <input id="f-headless" type="checkbox" checked>
      <label for="f-headless">HEADLESS MODE</label>
    </div>

    <label>LOGIN MODE</label>
    <select id="f-login">
      <option value="none">NONE (NO LOGIN)</option>
      <option value="manual">MANUAL (VISIBLE BROWSER)</option>
      <option value="credentials">CREDENTIALS</option>
      <option value="storage_state">STORAGE STATE</option>
    </select>

    <div id="cred-fields" class="hidden">
      <label>LOGIN URL</label>
      <input id="f-login-url" type="text">
      <label>USERNAME SELECTOR</label>
      <input id="f-user-sel" type="text" placeholder="#username">
      <label>PASSWORD SELECTOR</label>
      <input id="f-pass-sel" type="text" placeholder="#password">
      <label>SUBMIT SELECTOR</label>
      <input id="f-submit-sel" type="text" placeholder="#login-btn">
      <label>USERNAME</label>
      <input id="f-user" type="text">
      <label>PASSWORD</label>
      <input id="f-pass" type="password">
    </div>

    <div id="storage-fields" class="hidden">
      <label>STORAGE STATE PATH</label>
      <input id="f-storage" type="text" placeholder="/path/to/state.json">
    </div>

    <div id="form-error" class="err hidden"></div>
    <button class="btn" type="submit" id="run-btn">RUN SCAN</button>
  </form>
</div>

<!-- ==================== SCAN OUTPUT SECTION ==================== -->
<div id="scan-section" class="hidden">
  <h2 id="scan-title">] SCANNING...</h2>
  <div class="output" id="output"></div>
  <button class="btn btn-amber hidden" id="continue-btn">CONTINUE (LOGIN DONE)</button>
</div>

<!-- ==================== REPORT SECTION ==================== -->
<div id="report-section" class="hidden">
  <h2>] REPORT COMPLETE</h2>
  <pre class="report" id="report-output"></pre>
  <br>
  <button class="btn" id="new-btn">NEW SCAN</button>
  <button class="btn btn-outline btn-sm" id="copy-btn" style="margin-left:8px">COPY REPORT</button>
  <button class="btn btn-outline btn-sm" id="json-btn" style="margin-left:8px">DOWNLOAD JSON</button>
</div>

<!-- Footer prompt -->
<div class="prompt" id="status-line">] READY <span class="cursor"></span></div>

</div></div></div>

<script>
/* ================================================================
   PENDO FEASIBILITY SCRAPER – LOCAL UI CONTROLLER
   ================================================================ */
const $ = s => document.querySelector(s);

// DOM refs
const formSection  = $('#form-section');
const scanSection  = $('#scan-section');
const reportSection= $('#report-section');
const output       = $('#output');
const statusLine   = $('#status-line');
const scanTitle    = $('#scan-title');
const continueBtn  = $('#continue-btn');
const runBtn       = $('#run-btn');
const formError    = $('#form-error');
const loginSelect  = $('#f-login');
const credFields   = $('#cred-fields');
const storageFields= $('#storage-fields');

let currentScanId = null;
let pollTimer     = null;
let lastLineCount = 0;

// Toggle credential/storage fields based on login mode
loginSelect.addEventListener('change', () => {
  const v = loginSelect.value;
  credFields.classList.toggle('hidden', v !== 'credentials');
  storageFields.classList.toggle('hidden', v !== 'storage_state');
  // Manual login forces headless OFF
  if (v === 'manual') {
    $('#f-headless').checked = false;
  }
});

// Submit scan
$('#scan-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  formError.classList.add('hidden');

  const url = $('#f-url').value.trim();
  if (!url) return;

  const loginMode = loginSelect.value;
  const headless  = loginMode === 'manual' ? false : $('#f-headless').checked;

  const config = {
    max_pages: parseInt($('#f-pages').value) || 12,
    headless,
    login_mode: loginMode === 'none' ? 'manual' : loginMode,
    login_url: $('#f-login-url')?.value || '',
    username_selector: $('#f-user-sel')?.value || '',
    password_selector: $('#f-pass-sel')?.value || '',
    submit_selector: $('#f-submit-sel')?.value || '',
    username: $('#f-user')?.value || '',
    password: $('#f-pass')?.value || '',
    storage_state_path: $('#f-storage')?.value || '',
  };

  // For "none" login mode, we still use manual mode internally
  // but auto-set the login event immediately via a flag.
  const autoLogin = loginMode === 'none';

  runBtn.disabled = true;
  runBtn.textContent = 'STARTING...';

  try {
    const res = await fetch('/api/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ target_url: url, config })
    });
    const data = await res.json();
    currentScanId = data.id;
    lastLineCount = 0;

    // If no login needed, immediately tell the server to continue
    if (autoLogin) {
      setTimeout(() => {
        fetch(`/api/scan/${currentScanId}/continue`, { method: 'POST' });
      }, 500);
    }

    showSection('scan');
    startPolling();
  } catch (err) {
    formError.textContent = '! FAILED TO START SCAN: ' + err.message;
    formError.classList.remove('hidden');
    runBtn.disabled = false;
    runBtn.textContent = 'RUN SCAN';
  }
});

// Continue button (manual login)
continueBtn.addEventListener('click', async () => {
  if (!currentScanId) return;
  continueBtn.disabled = true;
  continueBtn.textContent = 'CONTINUING...';
  await fetch(`/api/scan/${currentScanId}/continue`, { method: 'POST' });
  continueBtn.classList.add('hidden');
});

// New scan button
$('#new-btn').addEventListener('click', () => {
  showSection('form');
  output.innerHTML = '';
  $('#report-output').textContent = '';
  runBtn.disabled = false;
  runBtn.textContent = 'RUN SCAN';
  continueBtn.classList.add('hidden');
  continueBtn.disabled = false;
  continueBtn.textContent = 'CONTINUE (LOGIN DONE)';
  statusLine.innerHTML = '] READY <span class="cursor"></span>';
});

// Copy report
$('#copy-btn').addEventListener('click', () => {
  const text = $('#report-output').textContent;
  navigator.clipboard.writeText(text).then(() => {
    $('#copy-btn').textContent = 'COPIED!';
    setTimeout(() => { $('#copy-btn').textContent = 'COPY REPORT'; }, 2000);
  });
});

// Download JSON
$('#json-btn').addEventListener('click', async () => {
  if (!currentScanId) return;
  const res = await fetch(`/api/scan/${currentScanId}`);
  const data = await res.json();
  const blob = new Blob([JSON.stringify(data.report_json, null, 2)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'pendo_feasibility_report.json';
  a.click();
});

// --- Helpers ---

function showSection(name) {
  formSection.classList.toggle('hidden', name !== 'form');
  scanSection.classList.toggle('hidden', name !== 'scan');
  reportSection.classList.toggle('hidden', name !== 'report');
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollScan, 1500);
}

async function pollScan() {
  if (!currentScanId) return;
  try {
    const res = await fetch(`/api/scan/${currentScanId}`);
    const data = await res.json();

    // Render new progress lines
    const lines = data.progress || [];
    for (let i = lastLineCount; i < lines.length; i++) {
      const div = document.createElement('div');
      div.className = 'line';
      div.textContent = '] ' + lines[i];
      output.appendChild(div);
      output.scrollTop = output.scrollHeight;
    }
    lastLineCount = lines.length;

    // Show/hide continue button
    if (data.status === 'waiting_for_login') {
      continueBtn.classList.remove('hidden');
      scanTitle.textContent = '] WAITING FOR LOGIN...';
      statusLine.innerHTML = '] LOG IN VIA THE BROWSER WINDOW, THEN CLICK CONTINUE <span class="cursor"></span>';
    } else if (data.status === 'running') {
      scanTitle.textContent = '] SCANNING...';
      const lastMsg = lines.length > 0 ? lines[lines.length - 1] : 'WORKING...';
      statusLine.innerHTML = '] ' + lastMsg + ' <span class="cursor"></span>';
    }

    // Done
    if (data.status === 'done') {
      clearInterval(pollTimer);
      pollTimer = null;
      $('#report-output').textContent = data.report_text;
      showSection('report');
      statusLine.innerHTML = '] SCAN COMPLETE <span class="cursor"></span>';
    }

    // Error
    if (data.status === 'error') {
      clearInterval(pollTimer);
      pollTimer = null;
      const div = document.createElement('div');
      div.className = 'line';
      div.style.color = '#ff4444';
      div.textContent = '] ERROR: ' + (data.error || 'Unknown error');
      output.appendChild(div);
      statusLine.innerHTML = '] SCAN FAILED <span class="cursor"></span>';
      // Show new scan button in the scan section
      const retryBtn = document.createElement('button');
      retryBtn.className = 'btn';
      retryBtn.textContent = 'TRY AGAIN';
      retryBtn.style.marginTop = '16px';
      retryBtn.onclick = () => {
        showSection('form');
        output.innerHTML = '';
        runBtn.disabled = false;
        runBtn.textContent = 'RUN SCAN';
        statusLine.innerHTML = '] READY <span class="cursor"></span>';
      };
      scanSection.appendChild(retryBtn);
    }
  } catch {
    // Network blip – keep polling
  }
}
</script>
</body>
</html>
'''
