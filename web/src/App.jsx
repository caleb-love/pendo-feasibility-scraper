import React, { useEffect, useState, useRef } from 'react';
import { createScan, getMe, listScans } from './api.js';

/**
 * ASCII art banner styled after the Apple ][ boot screen.
 */
const ASCII_BANNER = `
 ____  _____ _   _ ____   ___
|  _ \\| ____| \\ | |  _ \\ / _ \\
| |_) |  _| |  \\| | | | | | | |
|  __/| |___| |\\  | |_| | |_| |
|_|   |_____|_| \\_|____/ \\___/
  FEASIBILITY  SCRAPER  //e
`.trimStart();

/**
 * Map scan status to a CSS class suffix.
 */
function statusClass(status) {
  if (!status) return '';
  const s = status.toLowerCase();
  if (s === 'queued') return 'status-queued';
  if (s === 'running' || s === 'in_progress') return 'status-running';
  if (s === 'done' || s === 'completed') return 'status-done';
  if (s === 'failed' || s === 'error') return 'status-failed';
  return '';
}

function App() {
  const [user, setUser] = useState(null);
  const [scans, setScans] = useState([]);
  const [targetUrl, setTargetUrl] = useState('');
  const [maxPages, setMaxPages] = useState(12);
  const [headless, setHeadless] = useState(true);
  const [loginMode, setLoginMode] = useState('manual');
  const [loginUrl, setLoginUrl] = useState('');
  const [usernameSelector, setUsernameSelector] = useState('');
  const [passwordSelector, setPasswordSelector] = useState('');
  const [submitSelector, setSubmitSelector] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [storageStatePath, setStorageStatePath] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => {
    getMe().then(setUser).catch(() => setUser(null));
    refreshScans();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  /**
   * Auto-poll for scan updates when any scan is still running.
   */
  useEffect(() => {
    const hasActive = scans.some(
      (s) => s.status === 'queued' || s.status === 'running' || s.status === 'in_progress'
    );
    if (hasActive && !pollRef.current) {
      pollRef.current = setInterval(refreshScans, 5000);
    } else if (!hasActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, [scans]);

  async function refreshScans() {
    try {
      const data = await listScans();
      setScans(data || []);
    } catch {
      /* network error – keep existing list */
    }
  }

  async function submitScan(e) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await createScan({
        target_url: targetUrl,
        config: {
          max_pages: Number(maxPages),
          headless,
          login_mode: loginMode,
          login_url: loginUrl,
          username_selector: usernameSelector,
          password_selector: passwordSelector,
          submit_selector: submitSelector,
          username,
          password,
          storage_state_path: storageStatePath,
        },
      });
      setTargetUrl('');
      await refreshScans();
    } catch {
      setError('SCAN INIT FAILED. CHECK INPUTS.');
    } finally {
      setSubmitting(false);
    }
  }

  /* ---- Login screen ---- */
  if (!user || !user.email) {
    return (
      <div className="monitor">
        <div className="screen">
          <div className="screen-content login-screen">
            <pre className="ascii-header">{ASCII_BANNER}</pre>
            <p>
              ] AUTHENTICATE WITH YOUR PENDO GOOGLE ACCOUNT TO CONTINUE_
            </p>
            <a className="btn" href="/auth/login">
              SIGN IN WITH GOOGLE
            </a>
            <div className="prompt-line" style={{ marginTop: 32 }}>
              ] <span className="cursor-blink" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  /* ---- Main screen ---- */
  return (
    <div className="monitor">
      <div className="screen">
        <div className="screen-content">
          {/* Header */}
          <div className="header-bar">
            <pre className="ascii-header">{ASCII_BANNER}</pre>
            <div className="user-info">
              {user.email}
              <a href="/auth/logout">[LOGOUT]</a>
            </div>
          </div>

          <hr className="divider" />

          {/* New Scan Form */}
          <div className="section">
            <h2>] NEW SCAN</h2>

            <form onSubmit={submitScan}>
              <label>TARGET URL</label>
              <input
                type="text"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="HTTPS://APP.EXAMPLE.COM"
                required
                autoFocus
              />

              <label>MAX PAGES</label>
              <input
                type="number"
                value={maxPages}
                onChange={(e) => setMaxPages(e.target.value)}
                min="1"
                max="50"
              />

              <div className="checkbox-row">
                <input
                  id="headless-check"
                  type="checkbox"
                  checked={headless}
                  onChange={(e) => setHeadless(e.target.checked)}
                />
                <label htmlFor="headless-check">HEADLESS MODE</label>
              </div>

              <label>LOGIN MODE</label>
              <select
                value={loginMode}
                onChange={(e) => setLoginMode(e.target.value)}
              >
                <option value="manual">MANUAL</option>
                <option value="credentials">CREDENTIALS</option>
                <option value="storage_state">STORAGE STATE</option>
              </select>

              {loginMode === 'credentials' && (
                <>
                  <label>LOGIN URL</label>
                  <input
                    type="text"
                    value={loginUrl}
                    onChange={(e) => setLoginUrl(e.target.value)}
                  />
                  <label>USERNAME SELECTOR</label>
                  <input
                    type="text"
                    value={usernameSelector}
                    onChange={(e) => setUsernameSelector(e.target.value)}
                  />
                  <label>PASSWORD SELECTOR</label>
                  <input
                    type="text"
                    value={passwordSelector}
                    onChange={(e) => setPasswordSelector(e.target.value)}
                  />
                  <label>SUBMIT SELECTOR</label>
                  <input
                    type="text"
                    value={submitSelector}
                    onChange={(e) => setSubmitSelector(e.target.value)}
                  />
                  <label>USERNAME</label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                  <label>PASSWORD</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </>
              )}

              {loginMode === 'storage_state' && (
                <>
                  <label>STORAGE STATE PATH</label>
                  <input
                    type="text"
                    value={storageStatePath}
                    onChange={(e) => setStorageStatePath(e.target.value)}
                  />
                </>
              )}

              {error && <div className="error-msg">! {error}</div>}

              <button className="btn" type="submit" disabled={submitting}>
                {submitting ? 'SCANNING...' : 'RUN SCAN'}
              </button>
            </form>
          </div>

          <hr className="divider" />

          {/* Recent Scans */}
          <div className="section">
            <div className="section-header">
              <h2>] RECENT SCANS</h2>
              <button
                className="btn btn-sm btn-outline"
                type="button"
                onClick={refreshScans}
              >
                REFRESH
              </button>
            </div>

            {scans.length === 0 && (
              <div className="empty-msg">NO SCANS FOUND. RUN ONE ABOVE.</div>
            )}

            {scans.map((scan) => (
              <div key={scan.id} className="scan-row">
                <div>
                  <div className="scan-url">{scan.target_url}</div>
                  <div className="scan-meta">
                    <span className={`status ${statusClass(scan.status)}`}>
                      {scan.status}
                    </span>
                    {' // '}
                    {scan.created_at}
                  </div>
                </div>
                <div className="scan-links">
                  {scan.report_text_path && (
                    <a
                      href={`/api/scans/${scan.id}/report`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      [TXT]
                    </a>
                  )}
                  {scan.report_json_path && (
                    <a
                      href={`/api/scans/${scan.id}/report.json`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      [JSON]
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Footer prompt */}
          <div className="prompt-line">
            ] READY. {scans.length} SCAN(S) ON FILE
            <span className="cursor-blink" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
