export async function getMe() {
  const res = await fetch('/api/me', { credentials: 'include' });
  return res.json();
}

export async function createScan(payload) {
  const res = await fetch('/api/scans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    throw new Error('Failed to create scan');
  }
  return res.json();
}

export async function listScans() {
  const res = await fetch('/api/scans', { credentials: 'include' });
  if (!res.ok) {
    return [];
  }
  return res.json();
}
