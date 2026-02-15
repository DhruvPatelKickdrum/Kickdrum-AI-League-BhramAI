# Claim Verifier – Chrome Extension

A simple Chrome extension that verifies selected text using the backend RAG claim verification API.

## Features

- **On/Off toggle**: Use the extension popup (click the extension icon) to turn verification on or off. When off, right-clicking "Verify claim" will prompt you to turn it on.
- **Context menu**: When the extension is on, select any text on a page, right-click, and choose **"Verify claim"**. The selected text is sent to the API and the result opens in a new tab (verdict, reasoning, citations).
- **API URL**: In the popup you can set the API base URL (default: `http://localhost:8080`). Use this if your backend runs on a different host/port.

## Setup

1. **Backend**: Start the backend (e.g. `./run_server.sh` or `python -m src.api.app`) so that `POST /verify` is available at the configured base URL.
2. **Load the extension**:
   - Open Chrome and go to `chrome://extensions/`.
   - Turn on **Developer mode** (top right).
   - Click **Load unpacked** and select this folder (`chrome-extension`).
3. **Optional**: Click the extension icon to open the popup. Turn the extension on/off and set the API base URL if needed.

## Usage

1. Ensure the extension is **on** (popup toggle).
2. On any webpage, select the full text you want to verify.
3. Right-click the selection and click **"Verify claim"**.
4. A new tab opens with the verification result (claim, verdict, reasoning, citations) or an error message if the API call failed.

## Files

- `manifest.json` – Extension manifest (Manifest V3).
- `background.js` – Service worker: context menu and `POST /verify` API call.
- `popup.html` / `popup.js` – Popup UI for on/off and API URL.
- `result.html` / `result.js` – Result page shown after verification.

## Permissions

- **contextMenus** – Right-click "Verify claim" on selected text.
- **storage** – Save on/off state and API URL.
- **notifications** – Show a message when the extension is off and user tries to verify.
- **host_permissions** – `http://localhost:8080/*` and `http://127.0.0.1:8080/*` to call the API.

To use a different host (e.g. production), add it in the manifest under `host_permissions` and set the same URL in the popup.
