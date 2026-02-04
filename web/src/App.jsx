import React, { useEffect, useState } from 'react';
import { createScan, getMe, listScans } from './api.js';

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

  useEffect(() => {
    // Load user and scans on mount.
    getMe().then(setUser).catch(() => setUser(null));
    refreshScans();
  }, []);

  async function refreshScans() {
    const data = await listScans();
    setScans(data || []);
  }

  async function submitScan(e) {
    e.preventDefault();
    setError('');
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
          storage_state_path: storageStatePath
        }
      });
      setTargetUrl('');
      await refreshScans();
    } catch (err) {
      setError('Failed to create scan. Check inputs and login mode.');
    }
  }

  if (!user || !user.email) {
    return (
      <div className="container">
        <h1>Pendo Feasibility Scraper</h1>
        <p>Please log in with your Pendo Google account.</p>
        <a className="button" href="/auth/login">Sign in with Google</a>
      </div>
    );
  }

  return (
    <div className="container">
      <header className="header">
        <h1>Pendo Feasibility Scraper</h1>
        <div className="user">
          {user.email}
          <a href="/auth/logout">Logout</a>
        </div>
      </header>
      
      <form className="card" onSubmit={submitScan}>
        <h2>New Scan</h2>
        <label>
          Target URL
          <input
            type="text"
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            placeholder="https://app.example.com"
            required
          />
        </label>
        <label>
          Max Pages
          <input
            type="number"
            value={maxPages}
            onChange={(e) => setMaxPages(e.target.value)}
            min="1"
            max="50"
          />
        </label>
        <label className="inline">
          <input
            type="checkbox"
            checked={headless}
            onChange={(e) => setHeadless(e.target.checked)}
          />
          Headless
        </label>
        <label>
          Login Mode
          <select value={loginMode} onChange={(e) => setLoginMode(e.target.value)}>
            <option value="manual">Manual</option>
            <option value="credentials">Credentials</option>
            <option value="storage_state">Storage State</option>
          </select>
        </label>
        {loginMode === 'credentials' && (
          <>
            <label>
              Login URL
              <input type="text" value={loginUrl} onChange={(e) => setLoginUrl(e.target.value)} />
            </label>
            <label>
              Username Selector
              <input type="text" value={usernameSelector} onChange={(e) => setUsernameSelector(e.target.value)} />
            </label>
            <label>
              Password Selector
              <input type="text" value={passwordSelector} onChange={(e) => setPasswordSelector(e.target.value)} />
            </label>
            <label>
              Submit Selector
              <input type="text" value={submitSelector} onChange={(e) => setSubmitSelector(e.target.value)} />
            </label>
            <label>
              Username
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} />
            </label>
            <label>
              Password
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
          </>
        )}
        {loginMode === 'storage_state' && (
          <label>
            Storage State Path
            <input type="text" value={storageStatePath} onChange={(e) => setStorageStatePath(e.target.value)} />
          </label>
        )}
        {error && <div className="error">{error}</div>}
        <button className="button" type="submit">Run Scan</button>
      </form>
      
      <section className="card">
        <div className="card-header">
          <h2>Recent Scans</h2>
          <button className="button" type="button" onClick={refreshScans}>Refresh</button>
        </div>
        {scans.length === 0 && <p>No scans yet.</p>}
        {scans.map((scan) => (
          <div key={scan.id} className="scan-row">
            <div>
              <strong>{scan.target_url}</strong>
              <div className="small">{scan.status} • {scan.created_at}</div>
            </div>
            <div className="links">
              {scan.report_text_path && (
                <a href={`/api/scans/${scan.id}/report`} target="_blank" rel="noreferrer">Text</a>
              )}
              {scan.report_json_path && (
                <a href={`/api/scans/${scan.id}/report.json`} target="_blank" rel="noreferrer">JSON</a>
              )}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}

export default App;
