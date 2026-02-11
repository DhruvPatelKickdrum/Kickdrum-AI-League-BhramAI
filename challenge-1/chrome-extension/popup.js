/**
 * Popup: on/off toggle and API base URL. Stored in chrome.storage.local.
 */

const STORAGE_KEYS = { enabled: 'enabled', apiBaseUrl: 'apiBaseUrl' };
const DEFAULT_API_BASE = 'http://localhost:8080';

const toggleEl = document.getElementById('toggle');
const apiUrlEl = document.getElementById('apiUrl');

async function load() {
  const { enabled, apiBaseUrl } = await chrome.storage.local.get([
    STORAGE_KEYS.enabled,
    STORAGE_KEYS.apiBaseUrl,
  ]);
  const isOn = enabled !== false;
  toggleEl.classList.toggle('on', isOn);
  toggleEl.setAttribute('aria-pressed', isOn);
  apiUrlEl.value = apiBaseUrl || DEFAULT_API_BASE;
}

function saveEnabled(on) {
  chrome.storage.local.set({ [STORAGE_KEYS.enabled]: on });
}

function saveUrl() {
  const url = (apiUrlEl.value || '').trim() || DEFAULT_API_BASE;
  chrome.storage.local.set({ [STORAGE_KEYS.apiBaseUrl]: url });
}

toggleEl.addEventListener('click', () => {
  const isOn = !toggleEl.classList.toggle('on');
  toggleEl.setAttribute('aria-pressed', isOn);
  saveEnabled(isOn);
});

toggleEl.addEventListener('keydown', (e) => {
  if (e.key === ' ' || e.key === 'Enter') {
    e.preventDefault();
    toggleEl.click();
  }
});

apiUrlEl.addEventListener('change', saveUrl);
apiUrlEl.addEventListener('blur', saveUrl);

load();
