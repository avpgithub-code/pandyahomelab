# AI Literacy Class — Registration Site · Status

_Last updated: 2026-06-01_

## TL;DR
The public registration site is **live and fully working end-to-end**. Visitors register → row lands in a Google Sheet → registrant gets a confirmation email + organiser gets a notification email.

**Live URL:** https://pandyahomelab.com/ai-literacy/

---

## What's done ✅

| Area | Status | Notes |
|---|---|---|
| Registration page (design + form) | ✅ | Vibrant page matching the flyer |
| Data collection | ✅ | Form POSTs to Google Apps Script → appends a row to the Sheet |
| Spam protection | ✅ | Hidden `_gotcha` honeypot; `safe_()` blocks spreadsheet-formula / CSV-injection |
| Confirmation + notification emails | ✅ | State-aware; verified end-to-end (notify → `architpandya@yahoo.com`) |
| **Per-state (NJ/CA)** | ✅ | Required state selector; one state per registration |
| **Capacity + stand-by** | ✅ | Per-state capacity in `Config`; over capacity → Stand By (+position); dedup by email+state |
| **Admin dashboard** | ✅ | Counts, promote-next, cancel, mass email, open/close toggle, **CSV export + Open-in-Sheets**, **one-click stakeholder PDF report** (download/email, aggregate counts only) |
| **Multi-admin** | ✅ | `Admins` tab allowlist + Google sign-in (execute-as-user) |
| Prerequisites | ✅ | Paid Claude account + basic computer skills (laptop prereq removed) |
| Published publicly | ✅ | Static files in nginx web root, behind Cloudflare Tunnel |
| Version control | ✅ | All in GitHub `pandyahomelab` (`main`); latest commit `d976cb5` |
| **SMS (Phase D)** | ⬜ | Pending a Twilio account |

---

## Key locations

- **Live/deployed page:** `/volume1/pandya-homelab/website/ai-literacy/index.html`
- **Working/source copy:** `/volume1/subhag-ai/doc/reg_index.html`
- **Apps Script (backend):** `/volume1/subhag-ai/doc/Code.gs` — deployed as a Web App; redeploy via *Deploy → Manage deployments → New version* (keeps same `/exec` URL)
- **Google Sheet:** "AI Literacy Class — Registrations" (fileId `1NFz4Y-qoA-kUnmJuiS4i7xlP6B8EgXmVbp_P7WbRtjo`)
- **GitHub repo:** `github.com:avpgithub-code/pandyahomelab.git`

## How it flows
```
Visitor → pandyahomelab.com/ai-literacy/ (Cloudflare Tunnel → pandya-nginx → static file)
        → POST to Apps Script /exec
        → append row to Google Sheet
        → email confirmation to registrant + notification to organiser
```

---

## ▶ Resume here — open items (nothing is a blocker; all defaults work today)

**Awaiting approval-team decisions** — see the **Decision Brief** (`doc/AI-Literacy-Decision-Brief.md`)
and the live **Decision Register** Google Sheet (fileId `1RwKBTw2Rb9KWqMY1uqrvw7tdPyr33Dyo2yCl4eRe87s`).
4 High-priority calls: **A2** (one person in both NJ & CA?), **C1+D3** (student cancellation/contact
channel), **C3** (promote on cancel: manual vs auto). After sign-off, send chosen options → implement
(mostly small: an email "reply to fix/cancel" line, a phone-dup flag, an `Attended` status, a cross-location rule).

**Deferred:** Phase D — Twilio **SMS** (on the back burner; trial only texts verified numbers).

**Content housekeeping:**
- [ ] Fill in **When / Where / Cost** per state in the `Config` tab when known.
- [ ] Delete any leftover test rows in the Sheet before launch.
- [ ] Add the live URL to the printed flyer.
- [ ] (Optional) walkthrough-video captions — drafted (`doc/claude-setup-captions.*`), not attached (timings may not match the real clip).

## 📚 Documentation set (team-facing)

| Document | Google link (shareable) | Repo backup |
|---|---|---|
| **Admin Handbook** | Doc `1OgoR0TVIRRGGbgtft8wj5citPBJJZK9QqKAv9WvoixQ` | `docs/AI-Literacy-Admin-Handbook.md` |
| **Promote Next — deep-dive** | Doc `1hGB6KG6NfAwMcB1Ww9VY9Xnq8FDnPupiwllewKWyYIw` | `docs/AI-Literacy-promote-next-howto.md` |
| **Sheet Data Dictionary** | Sheet `1tiOm6yPoxVAXl5s7t0-CN44bc0ITYN3oZxEUGAbKDjQ` | `docs/AI-Literacy-sheet-design.md` |
| **Decision Register** | Sheet `1RwKBTw2Rb9KWqMY1uqrvw7tdPyr33Dyo2yCl4eRe87s` | `docs/AI-Literacy-Decision-Brief.md` (+ `open-decisions.md`) |
| **Migration Checklist** | Sheet `1IH_21Ia55CDZ23LxBdLrbXIjzMrtGUGr7NPB1MIPOWQ` | `docs/AI-Literacy-migration-guide.md` |
| **Documentation Summary** | Sheet `14phvZD8MzUCtCa9J5pK7N2a_IAF77GfozgUJ3fD712M` | `docs/AI-Literacy-Documentation-Summary.xlsx` |
| **Registrations (DATA)** | Sheet `1NFz4Y-qoA-kUnmJuiS4i7xlP6B8EgXmVbp_P7WbRtjo` | — |

Live: registration `https://pandyahomelab.com/ai-literacy/` · admin `https://pandyahomelab.com/ai-literacy/admin/`

## Improvements requested (agreed design — 2026-06-01)

**Progress:** Phase A (Sheet schema) ✅, Phase B (capacity + stand-by + dedup + state selector) ✅, **Phase C (admin dashboard)** ✅ — a separate standalone Apps Script web app (files: `admin-Code.gs` + `admin-Index.html`, HTML file named `Index`), reads the Sheet by ID; per-state cards, mass email to Registered, manual Promote-next + Cancel, per-state **Open/Close registration toggle** (writes `Config!RegOpen`), and **CSV export + Open-in-Sheets** on the grid. **Multi-admin** via the `Admins` tab, deployed **Execute-as-User-accessing / Anyone-with-a-Google-Account** with an allowlist check (see Admin access model below). Clean admin entry URL: **pandyahomelab.com/ai-literacy/admin/** (static launcher that redirects to the Apps Script app). Remaining: **Phase D** (Twilio SMS + SMS-consent checkbox).

**Source of truth / backups:** Apps Script source is version-controlled in the `pandyahomelab` git repo under `ai-literacy-apps-script/` (public backend, admin backend, admin UI) — these live OUTSIDE the nginx web root so they aren't publicly served. The live web pages are at `website/ai-literacy/index.html` (registration) and `website/ai-literacy/admin/index.html` (admin launcher).

### Admin access model
- **Multiple admins** supported via an **`Admins` tab** in the Sheet (column A = email). Add/remove admins by editing that tab — no code change, no redeploy. `setupAdmins()` (run once) creates the tab + seeds the owner.
- Admin Web App deployed **Execute as: User accessing** + **Who has access: Anyone with a Google Account**; `isAdmin_()` checks the signed-in email against the `Admins` tab. Non-listed accounts get an "Access denied" page. Each admin also needs **Editor** access to the Sheet (the app runs as them).

### Admin URLs
- Registration backend Web App (`/exec`): `…AKfycbywkXc4…` (public, "Anyone")
- Admin dashboard Web App (`/exec`): `…AKfycbykAKmi…` (allowlist via Admins tab; execute-as-user)  ← current
- Admin entry (clean): https://pandyahomelab.com/ai-literacy/admin/

Three modifications, with decisions locked:

### 1. Capacity & Stand-By
- Capacity stored **per-state** in a new `Config` tab in the Sheet (admin-editable, not in code).
- On submit, backend (inside its lock) compares `Registered` count vs capacity for that state:
  - under capacity → `Status = Registered` + confirmation email/SMS
  - at/over capacity → `Status = Stand By` + standby email/SMS, with the person's stand-by position (#N)
- Adds a `Status` column (`Registered` / `Stand By` / `Cancelled`) and **dedup by email+state** (no double seats).
- Race-safe via existing `LockService` lock.

### 2. Training by State (NJ / CA)
- **State is a required radio choice** (New Jersey / California) — one state per registration, mutually exclusive (NJ registrant never lands under CA).
- `Config` tab holds per-state **Capacity / RegOpen / When / Where / Cost**; the page shows state-specific details once a state is picked (retires the "To be announced" placeholders, admin-controlled).
- Sheet: add `State` + `Status` columns; new `Config` tab; new `Dashboard` tab (live counts).

### 3. Admin page  → **DECISION: Apps Script HtmlService dashboard**
- Secured by **Google sign-in restricted to allowlisted account(s)** (stronger than Basic Auth; no shared password). Linked from the site; URL is a script.google.com address.
- **3a Dashboard:** per-state cards — Capacity, Total Registered, Total Stand By, Seats remaining, % full — + filterable registrant table.
- **3b Mass updates:** → **DECISION: Email + SMS.** Email via MailApp (working). **SMS via Twilio** (UrlFetchApp) — requires a Twilio account + an SMS-consent checkbox at signup; Twilio creds go in **Script Properties (secret), NOT the Sheet**.
- **3c Promote stand-by:** → **DECISION: Manual one-click.** Admin clicks "Promote next" → earliest Stand-By becomes Registered (first-come) + auto email/SMS "a spot opened — you're in!".

### Extra improvements folded in
- Per-state registration open/close toggle (`RegOpen`).
- Stand-by position shown to the user.
- Capacity editable from the Admin page (writes the Config cell).

### Dependency on Archit
- A **Twilio account** (Account SID, Auth Token, From number) is needed before SMS can be enabled. Email works without it.

---

## Editing & re-publishing cheatsheet
1. Edit the source: `/volume1/subhag-ai/doc/reg_index.html`
2. Re-publish: copy it to `/volume1/pandya-homelab/website/ai-literacy/index.html` (goes live immediately — static file, no restart)
3. Commit:
   ```sh
   cd /volume1/pandya-homelab
   git add website/ai-literacy/index.html
   git commit -m "Update AI Literacy registration page"
   git push
   ```
4. Backend (email/validation) changes go in `Code.gs` → paste into the Apps Script editor → **redeploy as New version**.
