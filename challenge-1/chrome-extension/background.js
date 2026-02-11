/**
 * Service worker: context menu "Verify" — opens loading tab; the loading page does the API fetch.
 * Fetch runs in the tab so it is not killed when the service worker goes to sleep during long requests.
 */

const CONTEXT_MENU_ID = 'claim-verifier-verify';
const STORAGE_KEYS = { enabled: 'enabled', apiBaseUrl: 'apiBaseUrl', lastResult: 'lastResult', pendingVerification: 'pendingVerification' };
const DEFAULT_API_BASE = 'http://localhost:8080';

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.remove(CONTEXT_MENU_ID, () => {
    chrome.contextMenus.create({
      id: CONTEXT_MENU_ID,
      title: 'Verify claim',
      contexts: ['selection'],
    });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== CONTEXT_MENU_ID) return;

  const selection = (info.selectionText || '').trim();
  if (!selection) return;

  const { [STORAGE_KEYS.enabled]: enabled } =
    await chrome.storage.local.get([STORAGE_KEYS.enabled]);

  if (enabled === false) {
    chrome.notifications?.create({
      type: 'basic',
      title: 'Claim Verifier',
      message: 'Turn the extension ON from the popup to verify claims.',
    }).catch(() => {});
    return;
  }

  const loadingUrl = chrome.runtime.getURL('loading.html');
  await chrome.storage.local.set({
    [STORAGE_KEYS.pendingVerification]: { claim: selection, ts: Date.now() },
  });
  await chrome.tabs.create({ url: loadingUrl });
});
