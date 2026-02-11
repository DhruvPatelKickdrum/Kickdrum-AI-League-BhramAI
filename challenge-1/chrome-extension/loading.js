/**
 * Runs in the loading tab: fetches /verify, then stores result and navigates to result.html.
 * Doing the fetch here (instead of the service worker) avoids the SW being killed during long requests.
 */

const STORAGE_KEYS = { apiBaseUrl: 'apiBaseUrl', lastResult: 'lastResult', pendingVerification: 'pendingVerification' };
const DEFAULT_API_BASE = 'http://localhost:8080';

function getPendingVerification() {
  return new Promise((resolve) => {
    chrome.storage.local.get([STORAGE_KEYS.pendingVerification], (data) => resolve(data[STORAGE_KEYS.pendingVerification]));
  });
}

async function waitForPendingClaim(maxAttempts = 25, intervalMs = 50) {
  for (let i = 0; i < maxAttempts; i++) {
    const pending = await getPendingVerification();
    if (pending?.claim) return pending.claim;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return null;
}

(async function () {
  const claim = await waitForPendingClaim();
  await chrome.storage.local.remove(STORAGE_KEYS.pendingVerification);

  const { [STORAGE_KEYS.apiBaseUrl]: apiBaseUrl } = await chrome.storage.local.get([STORAGE_KEYS.apiBaseUrl]);

  if (!claim) {
    await chrome.storage.local.set({
      [STORAGE_KEYS.lastResult]: { error: 'No claim to verify. Use right‑click → Verify claim on selected text.', claim: '' },
    });
    window.location.href = chrome.runtime.getURL('result.html');
    return;
  }

  const base = (apiBaseUrl || DEFAULT_API_BASE).replace(/\/$/, '');
  const url = `${base}/verify`;

  let result;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ claim }),
    });
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      result = {
        error: data.error || res.statusText || `HTTP ${res.status}`,
        claim,
      };
    } else {
      result = {
        claim: data.claim || claim,
        verdict: data.verdict || '',
        reasoning: data.reasoning || '',
        citations: data.citations || [],
      };
    }
  } catch (err) {
    result = {
      error: err.message || 'Network error. Is the backend running at ' + base + '?',
      claim,
    };
  }

  await chrome.storage.local.set({ [STORAGE_KEYS.lastResult]: result });
  window.location.href = chrome.runtime.getURL('result.html');
})();
