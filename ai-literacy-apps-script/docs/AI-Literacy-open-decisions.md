# AI Literacy Class — Open Decisions & Operational Scenarios

_Parked for review with the approval team. Last updated: 2026-06-03_

This captures **policy/operational decisions** for the registration system — things the
software can support but that need a human/business decision. Each item lists **what happens
today**, the **options**, and a **recommendation**. Items marked **🔶 DECISION NEEDED** are open.

---

## 1. Duplicate prevention

**What happens today:** When a student submits, the backend checks existing rows and blocks a
**duplicate = same email + same Training Location** (case-insensitive, ignoring Cancelled rows).
The repeat submitter sees *"You're already on the list."* No extra row, no seat consumed. This
runs inside a lock, so two simultaneous submissions can't both slip through. ✅ (Tested.)

**What it does NOT catch (by design / limitation):**
- **Different email, same person** (e.g. Gmail one time, work email another) → two records.
- **Same name or same phone** → not blocked (names aren't unique; phones are optional/typo-prone).
- **Cross-location:** the same email *can* enroll in **both** NJ **and** CA (each location is a
  separate enrollment).

**🔶 DECISION NEEDED — cross-location policy:**
- **(a)** Leave as-is — one enrollment per (person, location); a person may join both NJ and CA.
- **(b)** One enrollment per person across the whole program — block a 2nd location for the same email.
- **(c)** Add **admin-side soft flagging** — highlight rows sharing a phone number so an admin can
  eyeball likely dupes (no auto-reject). Can combine with (a) or (b).

_Recommendation:_ (a) covers the real "clicked submit twice / re-registered" case well. Add (b) only
if attending both locations doesn't make sense. (c) is a cheap safety net worth adding either way.

---

## 2. Student made a typo (after confirmation)

**What happens today:** There is **no student self-service edit**. Fields can only be corrected by
an **admin** (edit the row in the Google Sheet directly, or — for status — via the dashboard).

**Special case — typo in their _email_:** the confirmation may have gone to the wrong/dead address
(or bounced), and we can't easily verify ownership. Admin correction is the safe path.

**Options for letting students request a fix:**
- **(i)** Add *"Need to fix a typo? Just reply to this email."* to the confirmation/stand-by emails
  → reply lands with the organiser, who edits the Sheet. **(Lightest, recommended.)**
- **(ii)** Show a contact email / mini "contact us" line on the page + confirmation.
- **(iii)** Build a self-service **edit link** (token-based lookup by email) — heavier; probably overkill.

_Recommendation:_ (i) + (ii). Admin edits on request; no new build needed beyond an email line.

**🔶 DECISION NEEDED:** confirm the **contact channel** (reply-to address / a dedicated email) to publish.

---

## 3. Student wants to cancel (after confirmation)

**What happens today:** **Admin-side cancellation already exists** — the dashboard's **Cancel**
button sets the row to `Cancelled` (frees a seat); the admin can then **Promote next** from stand-by.
What's missing is a clear **way for the student to request it.**

**Options for the request channel:**
- **(i)** *"Need to cancel? Reply to this email or contact us."* line in the confirmation email. **(Recommended.)**
- **(ii)** Published contact email on the page.
- **(iii)** Self-service **cancel link** (token-based) — heavier; optional later.

_Recommendation:_ (i)+(ii). Student requests → admin clicks Cancel → (optionally) Promote next.

**🔶 DECISION NEEDED:** when a registered student cancels and a seat frees up, should the next
stand-by be promoted **automatically** or **manually** (current: manual one-click)?

---

## 4. Other scenarios worth reviewing

| # | Scenario | Today | Suggested approach |
|---|---|---|---|
| 4.1 | **Switch location** (NJ ↔ CA) | Admin edits the `State` cell | Must re-check capacity for the new location (could land them on stand-by). Define as an admin task. |
| 4.2 | **Confirmation not received** (spam / typo'd email) | No auto-detect | Contact channel → admin verifies email + re-sends (or fixes). Tell students to check spam. |
| 4.3 | **Bounced / invalid email** | Not surfaced (MailApp doesn't easily report bounces) | Accept as a known gap; the contact channel covers it. |
| 4.4 | **"Delete my data" request** (privacy) | Admin deletes the row | Document a simple deletion process; matches the privacy note on the page. |
| 4.5 | **Withdraw from the stand-by list** | Admin sets Cancelled | Same channel/flow as a normal cancel. |
| 4.6 | **Raising capacity later** | Does **not** auto-promote stand-by | After raising capacity in `Config`, admin must **Promote next** for each freed seat. Note this. |
| 4.7 | **No-shows / attendance** | Not tracked | Optional: add an `Attended` / `No-show` status for follow-up & future invites. |
| 4.8 | **Registering on behalf of others** (one email, multiple people) | Dedup blocks the 2nd | Decide if group sign-ups are allowed; if so, needs a different rule. |
| 4.9 | **Schedule / venue change comms** | Admin **mass email** (works) | SMS deferred (Phase D). Mass email is the channel for now. |
| 4.10 | **Accessibility / special requests** | Captured in **Notes** | Make sure an admin reviews Notes before each session and acts on them. |

---

## 5. Decisions needed — quick checklist for the approval team

- [ ] **Cross-location:** allow both NJ & CA per person, or one enrollment per person? (§1)
- [ ] **Add phone-duplicate flagging** for admins? (§1c)
- [ ] **Contact channel** to publish for fixes/cancellations (reply-to / dedicated email)? (§2, §3)
- [ ] **Stand-by promotion** on cancellation: automatic or manual? (§3)
- [ ] **Track attendance** (`Attended`/`No-show`)? (§4.7)
- [ ] **Data-deletion** process wording? (§4.4)

> None of these are blockers — the system is live and working with sensible defaults today.
> These are refinements to confirm before/around launch.
