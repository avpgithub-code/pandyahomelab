# AI Literacy — Admin Guide: the **“Promote Next”** button

_Prepared 2026-06-04 · For admin team_

## 1. What it does (in one line)
**Promote Next** moves the **earliest person on a state’s Stand-By list up to Registered**, renumbers
everyone else in the queue, and **emails the promoted person** — all in one click. It is **manual**
(an admin triggers it) and **first-come-first-served**.

## 2. When to use it
- A **registered student cancels / drops out** → a seat frees up → promote the next stand-by.
- You **increased the Capacity** for a state (raising Capacity does **not** auto-promote — you promote
  the freed seats yourself).

## 3. Where the button is
On each **state card** (New Jersey / California) in the admin dashboard, beside “Close registration”.
It is **greyed-out when that state has 0 people on Stand-By** (nothing to promote).

```
┌─ New Jersey ──────────────── [Open] ┐
│  30/30   2   0                       │
│ Registered StandBy SeatsLeft         │
│ [ Promote next ]  [ Close registration ]
└──────────────────────────────────────┘
```

## 4. Step-by-step — what you do vs. what the system does

| # | You (admin) | What the system does behind the scenes |
|---|---|---|
| 1 | Open the admin dashboard, signed in as an allowlisted admin | Verifies your Google account is on the `Admins` tab |
| 2 | *(usually first)* Free a seat — click **Cancel** on the dropout’s row | Sets that row’s Status → `Cancelled` (Seats Left +1) |
| 3 | On the state card, click **Promote next** | — |
| 4 | Click **OK** on the confirm prompt | Begins the promotion |
| 5 | — | Takes a **lock** (stops two admins double-promoting at once) |
| 6 | — | Finds all `Stand By` rows for that state; sorts by **Standby Position**, then **Timestamp** |
| 7 | — | Picks the **earliest** one (the #1 in the queue) |
| 8 | — | Sets that row: **Status → Registered**, **Standby Position → blank** |
| 9 | — | **Renumbers** the remaining stand-by people (#2→#1, #3→#2, …) so the queue stays sequential |
| 10 | — | **Emails** the promoted person (“a spot opened — you’re in!”) with the session’s When/Where/Cost |
| 11 | See the green toast & updated numbers | Returns *“Promoted &lt;name&gt; to Registered (emailed).”* and refreshes the cards + table |

## 5. Who gets promoted (the selection rule)
The **earliest** person in the queue — ordered by **Standby Position** first, then **Timestamp** as a
tie-breaker. This is strict **first-come-first-served**.

## 6. What changes in the Sheet

| Field | Before | After |
|---|---|---|
| **Status** (promoted person) | `Stand By` | `Registered` |
| **Standby Position** (promoted person) | `1` | *(blank)* |
| **Standby Position** (everyone else in that state’s queue) | `2, 3, 4 …` | shifts up to `1, 2, 3 …` |
| Dashboard counts | — | **Registered +1**, **Stand By −1**, **Seats Left −1** |

## 7. The email the promoted person gets
- **Subject:** *“Good news — a spot opened up! AI Literacy Class (State)”*
- **Body:** they’ve been moved from stand-by to **registered**, plus the session **When / Where / Cost**
  (pulled live from the `Config` tab) and the prerequisites reminder.
- Sent from the acting admin’s Google account. If the email fails, the **promotion still applies**
  (status is already updated) — it never silently rolls back.

## 8. Important notes & edge cases

| Situation | Behaviour |
|---|---|
| **No one on Stand-By** | Button is disabled; if somehow called, returns *“No one is on the stand-by list for &lt;state&gt;.”* |
| **Capacity is NOT auto-checked** | Promote will push Registered **above** Capacity if you don’t free a seat first. **Best practice: Cancel a dropout (or raise Capacity) before promoting.** |
| **Multiple seats opened** | Promotes **one** person per click — click again for each additional seat |
| **Two admins at once** | The lock serializes it — the same person can’t be promoted twice |
| **Manual by design** | Auto-promote-on-cancel is a *pending decision* (see the Decision Register, ref C3) |

## 9. Related controls
- **Cancel** (row button) — frees a seat (the usual trigger for Promote Next).
- **Capacity / RegOpen** — in the `Config` tab (and the card’s Close/Open toggle).
- **Mass email** — to notify all Registered of changes.

---

### Quick recipe — “a student dropped out, fill the seat”
1. Find the dropout’s row → **Cancel**.
2. On that state’s card → **Promote next** → **OK**.
3. The next stand-by becomes Registered and gets the email. ✅
