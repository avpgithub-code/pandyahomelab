# AI Literacy Class — Registration System
## Decision Brief for the Approval Team

_Prepared 2026-06-03 · Owner: Archit Pandya · Status: for review_

---

### 1. Purpose & context
The online registration system is **live and working** (registration → Google Sheet → confirmation
email; admin dashboard with capacity, stand-by, promote, cancel, mass email, CSV export, multi-admin).
This brief lists the **operational / policy questions** that the software can support but that need a
**business decision** before or around launch. **None are blockers** — sensible defaults are already in place.

---

### 2. Concerns at a glance (coverage checklist)

**A. Enrollment integrity**
- A1. Duplicate registration — same email, same location *(handled)*
- A2. 🔶 Same person enrolling in **both** locations (NJ **and** CA)
- A3. Same person via **different emails** *(partial gap)*
- A4. **Phone-duplicate** soft flagging for admins *(optional)*
- A5. 🔶 **Group / on-behalf** sign-ups (one email, several people)

**B. Post-submission changes**
- B1. **Typo** correction (name / phone / experience)
- B2. **Email typo** (confirmation misdelivered or bounced)
- B3. **Switching location** (NJ ↔ CA)

**C. Cancellations & stand-by**
- C1. **Student-initiated cancellation**
- C2. **Withdraw from stand-by**
- C3. 🔶 Stand-by **promotion on cancel** — automatic vs manual
- C4. **Raising capacity** does not auto-promote stand-by *(process note)*

**D. Communications**
- D1. **Confirmation not received** (spam / typo)
- D2. **Schedule / venue change** comms
- D3. 🔶 **Contact channel** to publish (reply-to vs dedicated email)

**E. Attendance & follow-up**
- E1. 🔶 **No-show / attendance** tracking

**F. Data & privacy**
- F1. **"Delete my data"** requests
- F2. **Who can see the data** (admins = Sheet Editors) *(note)*

**G. Accessibility**
- G1. **Accessibility / special requests** captured in Notes — admin follow-up

> 🔶 = needs an approval-team decision · others are already handled or are process notes to acknowledge.

---

### 3. Detailed decision register

#### A. Enrollment integrity
| # | Concern | Current behaviour | Proposed action | Priority | Recommendation |
|---|---|---|---|---|---|
| A1 | Same email + same location twice | **Blocked** (dedup, race-safe); shows "already on the list" | Keep | — | ✅ Keep as-is |
| A2 | Same person in **both** NJ & CA | **Allowed** (each location = separate enrollment) | (a) allow both · (b) one per person across program | **High** | Decide by program intent; default = allow both |
| A3 | Same person, different emails | Not caught (2 records) | Accept as limitation; A4 helps spot it | Low | Accept; rely on A4 |
| A4 | Phone-duplicate flagging | None | Highlight rows sharing a phone for admin review (no auto-reject) | Medium | Add — cheap safety net |
| A5 | Group / on-behalf sign-ups | 2nd person on same email is blocked | Decide if group sign-ups allowed; if yes, needs a different rule | Medium | Default = one person per email |

#### B. Post-submission changes
| # | Concern | Current behaviour | Proposed action | Priority | Recommendation |
|---|---|---|---|---|---|
| B1 | Typo (name/phone/experience) | Admin edits the Sheet row | Add "reply to fix a typo" line to confirmation email | Medium | Admin-edit + email line |
| B2 | Email typo (confirmation bounced) | Admin corrects; no auto-detect | Same channel; ask students to check spam | Medium | Admin-edit on request |
| B3 | Switch location NJ ↔ CA | Admin edits `State` cell | Admin re-checks capacity for the new location (may → stand-by) | Low | Document as admin task |

#### C. Cancellations & stand-by
| # | Concern | Current behaviour | Proposed action | Priority | Recommendation |
|---|---|---|---|---|---|
| C1 | Student cancellation | Admin **Cancel** button (frees seat) — but no student channel | Add "reply to cancel / contact us" to confirmation + page | **High** | Add contact channel |
| C2 | Withdraw from stand-by | Admin sets Cancelled | Same flow as C1 | Low | Same channel |
| C3 | Promote on cancel | **Manual** one-click Promote | (a) manual · (b) automatic on cancel | **High** | Manual keeps control; confirm |
| C4 | Raising capacity | Does **not** auto-promote | Admin clicks Promote for each freed seat | Low | Document; optional auto later |

#### D. Communications
| # | Concern | Current behaviour | Proposed action | Priority | Recommendation |
|---|---|---|---|---|---|
| D1 | Confirmation not received | No auto-detect | Contact channel → admin verifies/re-sends; "check spam" note | Medium | Contact channel covers it |
| D2 | Schedule / venue change | Admin **mass email** (works) | Use mass email; SMS deferred (Phase D) | Low | ✅ Available |
| D3 | Contact channel to publish | Confirmation sends from organiser Gmail (reply works) | Pick reply-to vs a dedicated inbox; publish it | **High** | Decide the address to publish |

#### E. Attendance & follow-up
| # | Concern | Current behaviour | Proposed action | Priority | Recommendation |
|---|---|---|---|---|---|
| E1 | No-show / attendance | Not tracked | Optional `Attended` / `No-show` status for follow-up & future invites | Medium | Add if you'll run multiple cohorts |

#### F. Data & privacy
| # | Concern | Current behaviour | Proposed action | Priority | Recommendation |
|---|---|---|---|---|---|
| F1 | "Delete my data" request | Admin deletes the row | Document a simple deletion process (matches page privacy note) | Medium | Document SLA (e.g. within X days) |
| F2 | Who sees the data | Admins are Sheet **Editors** (can view/export) | Keep admin list tight (Admins tab); review periodically | Low | Note in onboarding |

#### G. Accessibility
| # | Concern | Current behaviour | Proposed action | Priority | Recommendation |
|---|---|---|---|---|---|
| G1 | Accessibility / special requests | Captured in **Notes** field | Admin reviews Notes before each session and acts | Medium | Add to pre-session checklist |

---

### 4. Recommended defaults (if the team just wants to approve a baseline)
1. **Dedup:** keep email+location; **allow** both NJ & CA per person (revisit if needed).
2. **Edits & cancellations:** admin-handled; add a **"reply to this email to fix a typo or cancel"** line + publish a contact address.
3. **Stand-by promotion:** keep **manual**.
4. **Add:** phone-duplicate flagging (A4) + a documented **data-deletion** process (F1).
5. **Optional now / later:** attendance tracking (E1) once there's a 2nd cohort; SMS (Phase D) when Twilio is upgraded.

---

### 5. Open decisions — sign-off checklist
| Ref | Decision | Options | Decision | Owner | Date |
|---|---|---|---|---|---|
| A2 | One person in both locations? | allow both / one per person | | | |
| A5 | Allow group sign-ups? | yes / no | | | |
| C3 | Promote on cancel | manual / automatic | | | |
| D3 | Public contact address | reply-to / dedicated inbox | | | |
| E1 | Track attendance? | yes / no | | | |
| A4 | Phone-duplicate flagging? | yes / no | | | |
| F1 | Data-deletion SLA wording | …days | | | |

---

### 6. How to present this to the approval team (recommended)
- **Best format:** a **shared “Decision Register” Google Sheet** (one row per item; the team fills
  *Decision / Owner / Status* columns live). It’s tabular, sortable, and captures sign-off in one place
  — better than a static doc for an approval meeting.
- **Meeting:** a single **30-minute review**, focused on the **4 High-priority** items (A2, C3, D3 + publishing the contact address). Everything else has a safe default.
- **Circulate this brief beforehand** (PDF or Google Doc) for context; use the Sheet during the meeting for decisions.
- **After sign-off:** send me the chosen options and I’ll implement (most are small — an email line, a status column, or a dedup rule).
