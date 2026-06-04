# AI Literacy Class — Hosting / Domain Migration Checklist

_Prepared 2026-06-04 · For team review · Status: planning_

---

## 1. TL;DR
Migrating to a **new host and/or new public domain** is a **low-risk static-site move**. Only the
**web pages** live on pandyaHomeLab; the data, logic, and email are **Google-hosted and
domain-independent**, so they don't move and keep working unchanged. In most cases this is:
**move ~4 files + 1 video → point DNS/TLS → retest** (plus an optional 2-line code edit).

---

## 2. What moves vs. what stays

| Component | Lives on | Moves? |
|---|---|---|
| Registration page, admin launcher, setup page + walkthrough video | pandyaHomeLab nginx web root (`website/ai-literacy/`) | ✅ **Move these** |
| Registration backend (Google Apps Script `/exec`) | Google | ❌ Unchanged — same URL |
| Admin dashboard (Apps Script) | Google | ❌ Unchanged |
| Google Sheet (Registrations / Config / Admins / Dashboard) | Google Drive | ❌ Unchanged |
| Confirmation / notification emails (MailApp) | Google account | ❌ Unchanged |

**Files to move** (the whole `website/ai-literacy/` folder):
- `index.html` (registration page)
- `claude-setup/index.html` + `claude-setup/walkthrough.mp4`
- `admin/index.html` (launcher → redirects to Google; works on any domain)

---

## 3. Decisions to make first
- [ ] **New domain name** registered (e.g. `ailiteracyclass.org`).
- [ ] **New host** chosen:
  - **Managed static host** (Cloudflare Pages / Netlify / Vercel / GitHub Pages / S3+CloudFront) — *easiest; recommended* for pure-static pages.
  - **Self-host** (new nginx + Cloudflare Tunnel) — same model as today.
  - **VPS / cloud nginx.**
- [ ] **URL structure:**
  - **Keep `/ai-literacy/` sub-path** → **zero code changes.**
  - **Serve at domain root** (`newdomain.com/`) → requires the 2 link edits in §5.
- [ ] **TLS / HTTPS** approach (managed host auto-HTTPS, Let's Encrypt, or Cloudflare).
- [ ] **Email sender** — keep sending from the current Google account (no change), or set up a
  branded custom-domain sender later (*optional, separate effort*).

---

## 4. Migration steps (checklist)

### Phase 1 — Prepare files
- [ ] Copy the `website/ai-literacy/` files to the new project/repo.
- [ ] If serving at **root**, apply the §5 link edits; if keeping `/ai-literacy/`, skip.
- [ ] Confirm relative references intact (the video `src="walkthrough.mp4"` sits beside the page).

### Phase 2 — Stand up the new host
- [ ] Create the hosting project / server.
- [ ] Deploy the static files.
- [ ] Confirm pages load on the host's temporary/preview URL (before DNS).

### Phase 3 — Domain, DNS, TLS, ingress
- [ ] Point the **domain's DNS** at the new host.
- [ ] Enable **HTTPS/TLS** for the new domain.
- [ ] Confirm internet ingress (managed host handles it; or new Cloudflare Tunnel route).
- [ ] **Lower DNS TTL** a day before cutover (faster rollback if needed).

### Phase 4 — Verify end-to-end on the new domain
- [ ] Registration **submit → row appears in the Google Sheet**.
- [ ] **Confirmation email** received; **notification email** received.
- [ ] **Capacity / stand-by** still behave (quick test).
- [ ] **Admin** URL loads + sign-in works; dashboard data shows.
- [ ] **Setup page** loads; **video plays**; "How to get one" link works.

### Phase 5 — Cutover & comms
- [ ] **301 redirect** `pandyahomelab.com/ai-literacy/*` → new domain (don't break old links/QR).
- [ ] Update **flyer / QR / printed materials / any shared links** to the new URL.
- [ ] Announce the new URL to stakeholders.

### Phase 6 — Post-migration
- [ ] Monitor the first real registrations on the new domain.
- [ ] Decommission the old pandyaHomeLab route (after a stable period).
- [ ] Update `STATUS.md`, the repo, and project notes with the new URLs.

---

## 5. Code-change reference (only if serving at domain ROOT)
Two internal absolute links to update; everything else is relative or external:

| File | Change from | Change to |
|---|---|---|
| `index.html` (form help link) | `href="/ai-literacy/claude-setup/"` | `href="/claude-setup/"` |
| `claude-setup/index.html` ("Back to registration") | `href="/ai-literacy/"` | `href="/"` |

*(Keeping the `/ai-literacy/` sub-path on the new domain = no edits at all.)*
External/unchanged: the Apps Script `/exec` URLs, the admin launcher's redirect, the
"Open in Google Sheets" link, and Google Fonts.

---

## 6. Do **NOT** touch (no-migration list)
- ❌ Apps Script Web Apps (registration backend + admin) — same `/exec` URLs, no redeploy.
- ❌ The Google Sheet (data + Config + Admins + Dashboard).
- ❌ Email configuration (still sends from the Google account).
- ❌ The admin allowlist (`Admins` tab) / sharing.
- ❌ No data migration of any kind.

> Why it's safe: the form POSTs to Google from **any** origin (no CORS allowlist), so a new
> domain "just works" against the existing backend.

---

## 7. Rollback safety
- Keep the **old host live** until the new domain is fully verified.
- Use a **low DNS TTL** so you can revert quickly.
- Apply the **301 redirect only after** end-to-end verification passes.
- Because the backend never changes, rollback = point DNS back; **no data risk**.

---

## 8. Sign-off
| Step / Phase | Owner | Target date | Status |
|---|---|---|---|
| Decisions (§3) | | | |
| Host + deploy (Ph 1–2) | | | |
| Domain/DNS/TLS (Ph 3) | | | |
| Verify (Ph 4) | | | |
| Cutover + comms (Ph 5) | | | |
| Post-migration (Ph 6) | | | |
