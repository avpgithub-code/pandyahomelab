# AI Literacy Class — "Registrations" Google Sheet · Design / Data Dictionary

_Prepared 2026-06-04 · For team onboarding_

This explains how the **AI Literacy Class — Registrations** Google Sheet is structured: every tab and
every field, what writes it, its allowed values, and the **design function** (why it exists / how the
system uses it).

**The Sheet is the single source of truth.** It has 4 tabs:
| Tab | Purpose | Who writes it |
|---|---|---|
| **Registrations** | One row per signup | The form + backend logic + admins |
| **Config** | Per-state settings (capacity, dates, open/closed) | **Admins** (edit cells) |
| **Dashboard** | Live counts (read-only) | **Formulas** (auto) |
| **Admins** | Who may use the admin dashboard | **Owner/admins** |

**"Set by" legend:** 👤 Registrant (via form) · ⚙️ Backend (Apps Script, automatic) · 🛠️ Admin (manual / dashboard) · ƒ Formula.

---

## 1. Tab: `Registrations` — one row per signup

| Column | What it holds | Set by | Allowed values / format | Design function |
|---|---|---|---|---|
| **Timestamp** | When the person submitted | ⚙️ | Date-time | Ordering; **first-come** stand-by order; audit trail |
| **State** | Training location chosen | 👤 (required) | `New Jersey` / `California` | Drives capacity, dedup, emails, dashboard grouping; one location per row |
| **Status** | Enrollment state | ⚙️ then 🛠️ | `Registered` / `Stand By` / `Cancelled` | The core lifecycle flag — counts, seat availability, who's actually in |
| **Standby Position** | Place in the wait queue | ⚙️ (renumbered on promote) | Number, or blank if Registered | Shows queue order; supports first-come promotion |
| **First** | First name | 👤 (required) | Text | Identification; email personalization |
| **Last** | Last name | 👤 (required) | Text | Identification |
| **Email** | Email address — **the dedup key** | 👤 (required, validated) | Valid email | Confirmation/stand-by emails; **dedup (email + State)**; mass email; contact |
| **Phone** | Phone number | 👤 (optional) | Text (`+` country code ok) | Contact; future SMS (Phase D); proposed phone-duplicate flagging |
| **AI Level** | Self-rated experience | 👤 (required) | Complete beginner / Tried a few times / Use occasionally / Fairly comfortable | Tailor class depth; analytics |
| **How Heard** | Acquisition source | 👤 (optional) | Flyer / poster · Friend or colleague · Email · Other | Marketing analytics |
| **Prereq: Claude** | Confirmed a paid Claude account | 👤 (required checkbox) | `Yes` / `No` | Readiness gate (must tick to submit → effectively always `Yes`) |
| **Prereq: Basic skills** | Confirmed basic computer skills | 👤 (required checkbox) | `Yes` / `No` | Readiness gate |
| **Notes** | Free text (accessibility / questions) | 👤 (optional) | Text | Special requests → admin follow-up before the session |
| **SMS Consent** | Consent to receive texts | 👤 | `Yes` / `No` | Reserved for **Phase D (SMS)** compliance; checkbox not yet on the form |
| **Marketing Opt-in** | Wants updates about future sessions | 👤 (checkbox, default on) | `Yes` / `No` | Future-session marketing list |

> Note: a safety routine (`safe_()`) neutralizes any value starting with `= + - @` to prevent
> spreadsheet-formula / CSV-injection (e.g. phone numbers beginning with `+`).

---

## 2. Tab: `Config` — per-state settings (admin-editable)

One row per state. **Admins edit these cells** to control the program; the backend reads them live.

| Column | What it holds | Set by | Allowed values / format | Design function |
|---|---|---|---|---|
| **State** | Location name | 🛠️ | `New Jersey` / `California` | Key that links Config ↔ Registrations ↔ Dashboard (must match exactly) |
| **Capacity** | Seat limit for that state | 🛠️ | Whole number (e.g. 30) | Backend compares Registered count vs this → Registered or Stand By; feeds Seats Left |
| **RegOpen** | Is registration open? | 🛠️ (or admin toggle) | `Yes` / `No` | If `No`, backend rejects new signups (status `closed`) and the page shows "closed" |
| **When** | Session date/time | 🛠️ | Text | Shown on the page (when state picked) + in emails; default "To be announced" |
| **Where** | Venue / location | 🛠️ | Text | Shown on the page + emails |
| **Cost** | Price / fee | 🛠️ | Text | Shown on the page + emails |

---

## 3. Tab: `Dashboard` — live counts (read-only, formula-driven)

Auto-calculated; **do not type over the formulas.** Layout: a title, a header row, one row per state, and a TOTAL row.

| Column | What it shows | Set by | How it's computed | Design function |
|---|---|---|---|---|
| **State** | Location label | ƒ | Static | Row label |
| **Capacity** | Seat limit | ƒ | `VLOOKUP` from `Config` | At-a-glance limit |
| **Registered** | # confirmed | ƒ | `COUNTIFS` Registrations: State = x AND Status = Registered | Live enrolled count |
| **Stand By** | # waitlisted | ƒ | `COUNTIFS` Status = Stand By | Live wait-list size |
| **Seats Left** | Remaining seats | ƒ | Capacity − Registered | Quick availability |
| **RegOpen** | Open/closed | ƒ | `VLOOKUP` from `Config` | Status mirror |
| **TOTAL** (row) | Program totals | ƒ | Sums of the columns | Overall snapshot |

> The admin dashboard web app computes its own live numbers too; this tab is the **Sheet-native** view for anyone who opens the spreadsheet directly.

---

## 4. Tab: `Admins` — who may use the admin dashboard

| Column | What it holds | Set by | Allowed values / format | Design function |
|---|---|---|---|---|
| **Admin Email** | A Google account allowed into the admin dashboard | 🛠️ Owner/admins | One email per row (lowercase) | The **allowlist** — the admin app checks the signed-in user's email against this tab; not listed → "Access denied" |

> Adding an admin = **(1)** add their email here **+ (2)** share this Sheet with them as **Editor**
> (the admin app runs *as* the signed-in admin, so they need access to the data).

---

## 5. How the data flows (one-paragraph mental model)
A visitor fills the form → the **backend** validates, checks the `Config` capacity + dedup, writes a
row to **Registrations** (Status = Registered or Stand By), and emails them. **Admins** manage the
program by editing **Config** (capacity, dates, open/close) and using the dashboard (promote, cancel,
mass email, export). **Dashboard** reflects everything live via formulas. **Admins** tab gates who can
do all that.
