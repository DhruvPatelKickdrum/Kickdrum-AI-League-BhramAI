/**
 * Result page: reads lastResult from storage and renders claim, verdict, reasoning, citations (or error).
 */

const STORAGE_KEY = 'lastResult';

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function render(result) {
  const content = document.getElementById('content');
  if (!result) {
    content.innerHTML = '<p class="error">No result data. Select text, right‑click → "Verify claim" to verify.</p>';
    return;
  }

  const { claim, verdict, reasoning, citations, error } = result;

  if (error) {
    content.innerHTML = `
      <div class="claim">${escapeHtml(claim || '')}</div>
      <div class="error">${escapeHtml(error)}</div>
    `;
    return;
  }

  const verdictClass = (v) => {
    if (!v) return '';
    const lower = String(v).toLowerCase();
    if (lower.includes('support') || lower === 'true') return 'supported';
    if (lower.includes('refut') || lower === 'false') return 'refuted';
    return 'uncertain';
  };

  let citationsHtml = '';
  if (citations && citations.length > 0) {
    citationsHtml = `
      <div class="section">
        <div class="section-title">Citations</div>
        <ul class="citations">
          ${citations.map((c) => {
            const title = typeof c === 'string'
              ? c
              : (c.source_title || c.title || c.url || JSON.stringify(c)).slice(0, 120);
            const url = typeof c === 'object' ? (c.source_url || c.url) : (typeof c === 'string' && c.startsWith('http') ? c : '');
            const rawSnippet = typeof c === 'object' && c.relevant_snippet ? String(c.relevant_snippet).trim() : '';
            const snippet = rawSnippet ? ` – ${rawSnippet.slice(0, 80)}${rawSnippet.length > 80 ? '…' : ''}` : '';
            return url
              ? `<li><a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(title)}</a>${escapeHtml(snippet)}</li>`
              : `<li>${escapeHtml(title)}${escapeHtml(snippet)}</li>`;
          }).join('')}
        </ul>
      </div>
    `;
  }

  content.innerHTML = `
    <div class="claim">${escapeHtml(claim || '')}</div>
    <div class="verdict ${verdictClass(verdict)}">${escapeHtml(verdict || '—')}</div>
    ${reasoning ? `
      <div class="section">
        <div class="section-title">Reasoning</div>
        <div class="reasoning">${escapeHtml(reasoning)}</div>
      </div>
    ` : ''}
    ${citationsHtml}
  `;
}

function loadAndRender() {
  chrome.storage.local.get([STORAGE_KEY], (data) => {
    const result = data[STORAGE_KEY];
    if (result != null) {
      render(result);
      return;
    }
    // Race: result page may load before background wrote storage; retry briefly
    let attempts = 0;
    const maxAttempts = 10;
    const interval = setInterval(() => {
      attempts += 1;
      chrome.storage.local.get([STORAGE_KEY], (retryData) => {
        if (retryData[STORAGE_KEY] != null) {
          clearInterval(interval);
          render(retryData[STORAGE_KEY]);
        } else if (attempts >= maxAttempts) {
          clearInterval(interval);
          render(null);
        }
      });
    }, 80);
  });
}

loadAndRender();
