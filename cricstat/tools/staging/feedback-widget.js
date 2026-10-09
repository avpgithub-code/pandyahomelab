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
 *   - Sends a page-view beacon to /feedback/pv, then engagement updates
 *     (active time, scroll depth, interactions) — see pageViewBeacon below
 *   - Records actions: demo runs (same-origin POSTs), example / About clicks,
 *     and anything a page sends via window.phl.track('name')
 *   - Records the widget's own funnel (v2, 2026-10-09): feedback:seen (the card scrolled
 *     into view, once per page view), feedback:like, feedback:open (form opened),
 *     feedback:sent (comment accepted) — so the dashboard shows view → click rates
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
  // A low like count reads as "nobody liked this", so the number only shows from this many likes up.
  const SHOW_COUNT_FROM = 3;
  function track(name) { try { if (window.phl && window.phl.track) window.phl.track(name); } catch (_) {} }

  // ─── Page-view / engagement beacon ─────────────────────────────────────
  // Tells the admin dashboard a real browser opened this page, and how long
  // the visitor stayed engaged. No cookies: a random tab-session id lives in
  // sessionStorage; the server keys visitors on its usual salted IP hash.
  //   engaged time  counts only while the tab is visible AND the visitor did
  //                 something (scroll / click / key / touch / mouse) in the last 30 s
  //   interactions  scrolls (max 1 per 2 s), clicks, key presses, touches
  (function pageViewBeacon() {
    const ENDPOINT = API_BASE + '/pv';
    const IDLE_MS = 30000;
    const VISIT_GAP_MS = 30 * 60 * 1000;

    function rid() {
      const a = new Uint8Array(8);
      crypto.getRandomValues(a);
      return Array.from(a, (b) => b.toString(16).padStart(2, '0')).join('');
    }

    function visitId() {
      const now = Date.now();
      let v = null;
      try { v = JSON.parse(sessionStorage.getItem('phl:visit') || 'null'); } catch (_) {}
      if (!v || typeof v.id !== 'string' || now - v.last > VISIT_GAP_MS) v = { id: rid() };
      v.last = now;
      try { sessionStorage.setItem('phl:visit', JSON.stringify(v)); } catch (_) {}
      return v.id;
    }

    function send(msg) {
      const body = JSON.stringify(msg);
      try {
        if (navigator.sendBeacon && navigator.sendBeacon(ENDPOINT, body)) return;
      } catch (_) {}
      try { fetch(ENDPOINT, { method: 'POST', body: body, keepalive: true }); } catch (_) {}
    }

    let pv, visit, engaged, lastTick, lastActive, maxScroll, interactions, lastScrollCount, sentKey;

    function scrollPct() {
      const doc = document.documentElement;
      const total = Math.max(doc.scrollHeight, document.body ? document.body.scrollHeight : 0);
      if (total <= window.innerHeight) return 100;
      return Math.min(100, Math.round((window.scrollY + window.innerHeight) / total * 100));
    }

    // Add the engaged time since the last tick, clipped to the 30 s idle window.
    function tick() {
      const now = Date.now();
      if (document.visibilityState === 'visible') {
        engaged += Math.max(0, Math.min(now, lastActive + IDLE_MS) - lastTick);
      }
      lastTick = now;
    }

    function activity(countIt) {
      tick();
      lastActive = Date.now();
      if (countIt) interactions++;
    }

    function update() {
      tick();
      maxScroll = Math.max(maxScroll, scrollPct());
      const key = engaged + ':' + maxScroll + ':' + interactions;
      if (key === sentKey) return;          // nothing new since the last beacon
      sentKey = key;
      send({ t: 'update', pv: pv, v: visit, e: engaged, s: maxScroll, i: interactions });
    }

    function start() {
      pv = rid();
      visit = visitId();
      engaged = 0;
      lastTick = lastActive = Date.now();
      maxScroll = 0;
      interactions = 0;
      lastScrollCount = 0;
      sentKey = '';
      const q = new URLSearchParams(window.location.search);
      send({
        t: 'start', pv: pv, v: visit, p: pageId,
        r: document.referrer || '',
        us: q.get('utm_source'), um: q.get('utm_medium'), uc: q.get('utm_campaign'),
        w: window.innerWidth, l: navigator.language || '',
      });
    }

    try {
      start();

      ['pointerdown', 'keydown', 'touchstart'].forEach((ev) =>
        window.addEventListener(ev, () => activity(true), { passive: true, capture: true }));
      window.addEventListener('scroll', () => {
        const now = Date.now();
        const counted = now - lastScrollCount > 2000;
        if (counted) lastScrollCount = now;
        activity(counted);
        maxScroll = Math.max(maxScroll, scrollPct());
      }, { passive: true });
      let lastMove = 0;
      window.addEventListener('mousemove', () => {
        const now = Date.now();
        if (now - lastMove > 1000) { lastMove = now; activity(false); }
      }, { passive: true });

      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
          update();
        } else {
          lastTick = lastActive = Date.now();   // coming back to the tab counts as activity
        }
      });
      window.addEventListener('pagehide', update);
      // Back/forward cache restore = a fresh page view of the same page
      window.addEventListener('pageshow', (e) => { if (e.persisted) start(); });
      // Heartbeat so long reads still land if the browser never fires pagehide (mobile)
      setInterval(() => { if (document.visibilityState === 'visible') update(); }, 15000);

      // ── Actions: what the visitor DID ──────────────────────────────────
      // Pages can call window.phl.track('name') directly; the common demo
      // actions below are picked up automatically, so no demo needs editing.
      function track(name) {
        name = String(name || '').toLowerCase().replace(/[^a-z0-9_:.-]/g, '-').slice(0, 40);
        if (name) send({ t: 'event', pv: pv, v: visit, n: name });
      }
      window.phl = window.phl || {};
      window.phl.track = track;

      // Every demo runs its model with a same-origin POST (/predict, /forecast,
      // /neighbors …), while model-info / about / history are GETs. A successful
      // POST → "run:<last path segment>". Our own /feedback/ calls are skipped.
      const origFetch = window.fetch;
      if (origFetch) {
        window.fetch = function (input, init) {
          const result = origFetch.apply(this, arguments);
          try {
            const isReq = typeof Request !== 'undefined' && input instanceof Request;
            const method = ((init && init.method) || (isReq ? input.method : 'GET')).toUpperCase();
            const url = new URL(isReq ? input.url : String(input), window.location.href);
            if (method === 'POST' && url.origin === window.location.origin
                && !url.pathname.startsWith(API_BASE + '/')) {
              const seg = url.pathname.replace(/\/+$/, '').split('/').pop() || 'post';
              result.then((r) => { if (r.ok) track('run:' + seg); }, () => {});
            }
          } catch (_) {}
          return result;
        };
      }

      document.addEventListener('click', (e) => {
        const t = e.target instanceof Element ? e.target : null;
        if (!t) return;
        if (t.closest('.example-btn')) track('example');
        else if (t.closest('#about-trigger')) track('about');
      }, { capture: true, passive: true });
    } catch (_) { /* analytics must never break the page */ }
  })();

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
    .phl-like-count[hidden] { display: none; }
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
    .phl-privacy {
      margin-top: 0.85rem;
      font-size: 0.72rem;
      color: #64748b;
    }
    .phl-privacy a { color: #64748b; }
    .phl-privacy a:hover { color: #4f8ef7; }
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
      + '      <span>👍</span><span data-role="like-label">Helpful</span><span class="phl-like-count" data-role="count" hidden></span>'
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
      + '  <div class="phl-privacy">No cookies · <a href="/privacy/">Privacy</a></div>'
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
      const label = widget.querySelector('[data-role="like-label"]');
      if (label && label.textContent === 'Helpful') label.textContent = 'Liked';
      likeBtn.classList.add('liked');
      likeBtn.disabled = true;
    }

    // Initial state — fetch count, restore liked from localStorage
    const likeLabel = $('like-label');
    function showCount(n) {
      const show = typeof n === 'number' && n >= SHOW_COUNT_FROM;
      countEl.hidden = !show;
      countEl.textContent = show ? String(n) : '';
    }
    showCount(await getLikeCount());

    // feedback:seen once per page view, when at least half the card is on screen
    try {
      if ('IntersectionObserver' in window) {
        const seen = new IntersectionObserver((entries) => {
          if (entries.some((e) => e.isIntersecting)) { track('feedback:seen'); seen.disconnect(); }
        }, { threshold: 0.5 });
        seen.observe(widget);
      }
    } catch (_) {}
    try { if (localStorage.getItem(LIKED_KEY)) markLiked(); } catch (_) {}

    // Like
    likeBtn.addEventListener('click', async () => {
      try {
        const data = await postLike();
        showCount(data.total_likes);
        likeLabel.textContent = 'Thanks';
        if (data.new_like) track('feedback:like');
        try { localStorage.setItem(LIKED_KEY, '1'); } catch (_) {}
        markLiked();
      } catch (e) {
        showMessage('Could not record like. Please try again.', 'error');
      }
    });

    // Toggle form
    toggleBtn.addEventListener('click', () => {
      form.classList.toggle('visible');
      if (form.classList.contains('visible')) { bodyEl.focus(); track('feedback:open'); }
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
        track('feedback:sent');
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
