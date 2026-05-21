/**
 * pandyaHomeLab feedback widget — likes + comments
 *
 * Single-file, self-contained. Embed via:
 *     <script src="/feedback-widget.js"></script>
 *
 * On load:
 *   - Reads window.location.pathname as page_id (normalised with trailing slash)
 *   - Appends widget DOM to document.body
 *   - Fetches current like count from /feedback/likes
 *   - Restores "already liked" state from localStorage
 *
 * User interactions:
 *   - Like button       → POST /feedback/likes, increment count, lock to "Liked ✓"
 *   - Share thoughts    → expand form
 *   - Submit comment    → POST /feedback/comments, show success or 429 message
 */
(function () {
  'use strict';

  // ─── Configuration ─────────────────────────────────────────────────────
  const API_BASE = '/feedback';
  let pageId = window.location.pathname;
  // Normalise: every page_id ends with /  (except root '/' itself is already correct)
  if (pageId !== '/' && !pageId.endsWith('/')) pageId += '/';
  const LIKED_KEY = 'phl:liked:' + pageId;

  // ─── Styles ────────────────────────────────────────────────────────────
  const css = `
    .phl-feedback {
      max-width: 760px;
      margin: 3rem auto 2rem;
      padding: 0 1rem;
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      box-sizing: border-box;
    }
    .phl-feedback *, .phl-feedback *::before, .phl-feedback *::after { box-sizing: border-box; }
    .phl-feedback-card {
      background: #13161e;
      border: 1px solid #252a38;
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
      color: #e2e8f0;
    }
    .phl-feedback-title {
      font-size: 0.92rem;
      font-weight: 700;
      color: #cbd5e1;
      margin-bottom: 0.85rem;
      display: flex;
      align-items: center;
      gap: 0.45rem;
    }
    .phl-feedback-actions {
      display: flex;
      gap: 0.65rem;
      flex-wrap: wrap;
      align-items: center;
    }
    .phl-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.5rem 1rem;
      border-radius: 99px;
      border: 1px solid rgba(79,142,247,0.35);
      background: rgba(79,142,247,0.08);
      color: #4f8ef7;
      font-size: 0.83rem;
      font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      transition: all 0.15s;
      line-height: 1;
    }
    .phl-btn:hover {
      background: rgba(79,142,247,0.18);
      border-color: #4f8ef7;
      transform: translateY(-1px);
    }
    .phl-btn:disabled {
      cursor: default;
      opacity: 0.8;
      transform: none;
    }
    .phl-btn-like.liked {
      background: rgba(34,197,94,0.15);
      border-color: rgba(34,197,94,0.45);
      color: #22c55e;
    }
    .phl-btn-like.liked:disabled { opacity: 1; }
    .phl-like-count {
      font-family: 'SF Mono', Consolas, monospace;
      font-weight: 700;
      font-size: 0.85rem;
      min-width: 1ch;
    }
    .phl-form {
      margin-top: 1rem;
      display: none;
    }
    .phl-form.visible { display: block; }
    .phl-input {
      width: 100%;
      padding: 0.55rem 0.75rem;
      background: #1a1e2a;
      border: 1px solid #252a38;
      border-radius: 6px;
      color: #e2e8f0;
      font-family: inherit;
      font-size: 0.85rem;
      margin-bottom: 0.65rem;
    }
    .phl-input:focus {
      outline: none;
      border-color: #4f8ef7;
    }
    .phl-textarea {
      resize: vertical;
      min-height: 90px;
      line-height: 1.5;
    }
    .phl-form-actions {
      display: flex;
      gap: 0.6rem;
      align-items: center;
      justify-content: flex-end;
    }
    .phl-char-count {
      font-size: 0.7rem;
      color: #64748b;
      margin-right: auto;
      font-family: 'SF Mono', Consolas, monospace;
    }
    .phl-btn-primary {
      background: #4f8ef7;
      border-color: #4f8ef7;
      color: #fff;
    }
    .phl-btn-primary:hover {
      background: #3a7ce0;
      border-color: #3a7ce0;
    }
    .phl-btn-primary:disabled {
      background: #252a38;
      border-color: #252a38;
      color: #64748b;
      cursor: not-allowed;
      transform: none;
    }
    .phl-message {
      margin-top: 0.85rem;
      padding: 0.6rem 0.85rem;
      border-radius: 6px;
      font-size: 0.82rem;
    }
    .phl-message.success {
      background: rgba(34,197,94,0.1);
      border-left: 2px solid #22c55e;
      color: #86efac;
    }
    .phl-message.error {
      background: rgba(248,113,113,0.1);
      border-left: 2px solid #f87171;
      color: #fca5a5;
    }
  `;

  // ─── DOM helpers ───────────────────────────────────────────────────────
  function injectStyles() {
    const el = document.createElement('style');
    el.setAttribute('data-phl-feedback', '1');
    el.textContent = css;
    document.head.appendChild(el);
  }

  function buildWidget() {
    const wrapper = document.createElement('div');
    wrapper.className = 'phl-feedback';
    wrapper.innerHTML = ''
      + '<div class="phl-feedback-card">'
      + '  <div class="phl-feedback-title">💬 Was this helpful?</div>'
      + '  <div class="phl-feedback-actions">'
      + '    <button type="button" class="phl-btn phl-btn-like" data-role="like">'
      + '      <span>👍</span><span class="phl-like-count" data-role="count">—</span>'
      + '    </button>'
      + '    <button type="button" class="phl-btn" data-role="toggle-form">✍️ Share thoughts</button>'
      + '  </div>'
      + '  <div class="phl-form" data-role="form">'
      + '    <input type="text" class="phl-input" data-role="name" placeholder="Your name (optional)" maxlength="80">'
      + '    <textarea class="phl-input phl-textarea" data-role="body" placeholder="What did you think?" maxlength="2000"></textarea>'
      + '    <div class="phl-form-actions">'
      + '      <span class="phl-char-count"><span data-role="char-count">0</span> / 2000</span>'
      + '      <button type="button" class="phl-btn phl-btn-primary" data-role="submit" disabled>Send</button>'
      + '    </div>'
      + '  </div>'
      + '  <div data-role="message"></div>'
      + '</div>';
    return wrapper;
  }

  // ─── API calls ─────────────────────────────────────────────────────────
  async function getLikeCount() {
    try {
      const r = await fetch(API_BASE + '/likes?page_id=' + encodeURIComponent(pageId));
      if (!r.ok) return null;
      const j = await r.json();
      return typeof j.total_likes === 'number' ? j.total_likes : null;
    } catch (_) { return null; }
  }

  async function postLike() {
    const r = await fetch(API_BASE + '/likes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page_id: pageId }),
    });
    if (!r.ok) throw Object.assign(new Error('like failed'), { status: r.status });
    return r.json();
  }

  async function postComment(name, body) {
    const r = await fetch(API_BASE + '/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page_id: pageId, name: name || null, body: body }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(j.detail || 'comment failed'), { status: r.status, detail: j.detail });
    return j;
  }

  // ─── Wire up ───────────────────────────────────────────────────────────
  async function init() {
    injectStyles();
    const widget = buildWidget();
    document.body.appendChild(widget);

    const $ = (role) => widget.querySelector('[data-role="' + role + '"]');
    const likeBtn = $('like'), countEl = $('count'), toggleBtn = $('toggle-form');
    const form = $('form'), nameEl = $('name'), bodyEl = $('body'), charEl = $('char-count');
    const submitBtn = $('submit'), messageEl = $('message');

    function showMessage(text, kind) {
      messageEl.innerHTML = '<div class="phl-message ' + kind + '">' + text + '</div>';
    }
    function clearMessage() { messageEl.innerHTML = ''; }
    function markLiked() {
      likeBtn.classList.add('liked');
      likeBtn.disabled = true;
    }

    // Initial state — fetch count, restore liked from localStorage
    const initial = await getLikeCount();
    countEl.textContent = initial === null ? '—' : String(initial);
    try { if (localStorage.getItem(LIKED_KEY)) markLiked(); } catch (_) {}

    // Like
    likeBtn.addEventListener('click', async () => {
      try {
        const data = await postLike();
        if (typeof data.total_likes === 'number') countEl.textContent = String(data.total_likes);
        try { localStorage.setItem(LIKED_KEY, '1'); } catch (_) {}
        markLiked();
      } catch (e) {
        showMessage('Could not record like. Please try again.', 'error');
      }
    });

    // Toggle form
    toggleBtn.addEventListener('click', () => {
      form.classList.toggle('visible');
      if (form.classList.contains('visible')) bodyEl.focus();
    });

    // Char counter + submit enable
    bodyEl.addEventListener('input', () => {
      const len = bodyEl.value.length;
      charEl.textContent = String(len);
      submitBtn.disabled = bodyEl.value.trim().length < 3;
    });

    // Submit
    submitBtn.addEventListener('click', async () => {
      const body = bodyEl.value.trim();
      const name = nameEl.value.trim();
      if (body.length < 3) return;

      submitBtn.disabled = true;
      const originalLabel = submitBtn.textContent;
      submitBtn.textContent = 'Sending…';
      clearMessage();

      try {
        const data = await postComment(name, body);
        showMessage(data.message || 'Thanks — your feedback was received.', 'success');
        nameEl.value = '';
        bodyEl.value = '';
        charEl.textContent = '0';
        // Auto-collapse after a few seconds
        setTimeout(() => {
          form.classList.remove('visible');
          clearMessage();
        }, 4500);
      } catch (e) {
        if (e.status === 429) {
          showMessage(e.detail || 'One comment per hour, please. Try again later.', 'error');
        } else {
          showMessage('Could not send. Please try again.', 'error');
        }
      } finally {
        submitBtn.textContent = originalLabel;
        submitBtn.disabled = bodyEl.value.trim().length < 3;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
