# AI Literacy — Apps Script sources (backup / source of truth)

These are reference copies of the Google Apps Script code that powers the
**AI Literacy Class** registration system. The *running* code lives in two
Google Apps Script projects (Google-hosted); these files are the version-controlled
source so the logic is never only in Google + a NAS folder.

> ⚠️ These files are intentionally **outside** `website/` so nginx never serves them publicly.

## Files
| File | What it is | Where it runs |
|---|---|---|
| `public-registration.gs` | Public registration backend (validate, capacity, stand-by, dedup, emails) | Apps Script project **bound to the Sheet**, deployed as Web App, access **Anyone** |
| `admin-dashboard.gs` | Admin backend (dashboard data, promote, cancel, mass email, open/close) | **Standalone** Apps Script project "AI Literacy — Admin", access **Only myself** |
| `admin-dashboard.Index.html` | Admin dashboard UI (HtmlService) — must be saved as an HTML file named **`Index`** | same standalone admin project |
| `STATUS.md` | Full project status snapshot | reference |

## Live web pages (in this repo, served by nginx)
- `website/ai-literacy/index.html` — public registration page → `pandyahomelab.com/ai-literacy/`
- `website/ai-literacy/admin/index.html` — launcher that redirects to the admin dashboard → `pandyahomelab.com/ai-literacy/admin/`

## Data
- Google Sheet **"AI Literacy Class — Registrations"**, fileId `1NFz4Y-qoA-kUnmJuiS4i7xlP6B8EgXmVbp_P7WbRtjo`
- Tabs: `Registrations`, `Config` (per-state Capacity / RegOpen / When / Where / Cost — admin-editable), `Dashboard` (live counts)

## Redeploy reminder
After editing any `.gs`/HTML in the Apps Script editor: **Deploy → Manage deployments → Edit → New version → Deploy** (keeps the same `/exec` URL). The HTML file in the admin project must be named `Index`.

## Pending
- **Phase D — SMS via Twilio** (Account SID / Auth Token / From number stored in Script Properties, never in the Sheet) + an SMS-consent checkbox at signup.
