AI LITERACY CLASS — ADMIN HANDBOOK
Prepared 2026-06-04 · For the admin team

================================================================
0. QUICK LINKS
================================================================
- Public registration page : https://pandyahomelab.com/ai-literacy/
- Admin dashboard           : https://pandyahomelab.com/ai-literacy/admin/
- Registrations Google Sheet (data) : https://docs.google.com/spreadsheets/d/1NFz4Y-qoA-kUnmJuiS4i7xlP6B8EgXmVbp_P7WbRtjo/edit
- Reference docs (see section 11 for the full list)

================================================================
1. OVERVIEW — WHAT THE ADMIN PORTAL IS
================================================================
The admin dashboard is a private control panel for the AI Literacy Class registrations.
From it you can: see live counts per location, promote stand-by students, cancel
registrations, open/close registration, email all registered students, and export the list.

How it fits together:
- Students register on the public page. Their details land in a Google Sheet.
- The dashboard reads and updates that same Sheet live.
- It is Google-hosted (the address ends in script.google.com); the clean entry link
  pandyahomelab.com/ai-literacy/admin/ simply forwards to it.

================================================================
2. GETTING IN (ACCESS & SIGN-IN)
================================================================
2.1  Open: https://pandyahomelab.com/ai-literacy/admin/
2.2  Sign in with the Google account that was added as an admin.
2.3  First time only: Google asks you to authorize the app — click Advanced, then
     "Go to AI Literacy — Admin", then Allow. (It is our own app, not malware.)
2.4  You should see the dashboard. The top shows "Signed in: <your email>".

If you see "ACCESS DENIED":
- You are signed into a Google account that is NOT on the admin list, OR
- You were not yet shared on the Sheet.
- Fix: an owner adds your email to the "Admins" tab AND shares the Sheet with you as
  Editor (see section 6). Make sure you are signed into the correct Google account.

================================================================
3. THE DASHBOARD AT A GLANCE
================================================================
3.1  STATE CARDS (one per location: New Jersey, California)
     - Registered (e.g. 12/30), Stand By, Seats left, % full bar, Open/Closed pill.
     - Buttons: "Promote next" and "Close/Open registration".
3.2  EMAIL PANEL — send an update to all registered students (all, or one state).
3.3  REGISTRATIONS TABLE — every signup, newest first.
     - Filters: by State and by Status.
     - Each active row has a "Cancel" button.
3.4  REFRESH (top right "↻") — reloads the latest numbers.
     Note: Refresh reloads DATA only. If the dashboard's layout/buttons ever look
     outdated, do a full browser refresh instead (Ctrl/Cmd + Shift + R).

================================================================
4. DAILY ACTIONS (RUNBOOKS)
================================================================

4.1  PROMOTE NEXT  (fill a freed seat from the wait-list)
     What it does: moves the EARLIEST stand-by person for that state up to Registered,
     renumbers the rest of the queue, and emails the promoted person. Manual, first-come.
     When: after a student cancels/drops, or after you raise capacity.
     Steps:
       1) (usually first) Cancel the dropout's row to free a seat — see 4.2.
       2) On the state card, click "Promote next".
       3) Confirm the prompt.
       4) The system picks the #1 stand-by, sets them Registered, clears their position,
          renumbers the others, and emails them ("a spot opened — you're in!").
       5) A toast confirms: "Promoted <name> to Registered (emailed)."
     Notes:
       - Greyed out when no one is on stand-by.
       - Capacity is NOT auto-checked — free a seat (Cancel) first, or you can exceed capacity.
       - Promotes ONE person per click.
     (Full deep-dive: AI-Literacy-promote-next-howto.md)

4.2  CANCEL A REGISTRATION  (a student drops out / requests cancellation)
     What it does: sets that row's Status to "Cancelled" and frees a seat.
     Steps:
       1) Find the person (use the State/Status filters or scan the table).
       2) Click "Cancel" on their row.
       3) Confirm. The row becomes Cancelled; Seats left increases by 1.
       4) If someone is waiting, follow with "Promote next" (4.1).
     Notes:
       - Cancelled rows are kept (not deleted) for the record. A cancelled person can
         register again later.
       - To permanently remove data (e.g. a deletion request), delete the row in the Sheet.

4.3  OPEN / CLOSE REGISTRATION  (stop or restart sign-ups for a location)
     What it does: flips that state's "RegOpen" switch in the Config tab.
     Steps:
       1) On the state card, click "Close registration" (red) to close, or "Open
          registration" to reopen.
       2) Confirm.
     Effect when CLOSED: the public page shows "Registration for <state> is currently
     closed" and the backend rejects new sign-ups for that state. Reopen anytime.
     Tip: close a location once its class is finished, so late visitors aren't confused.

4.4  EMAIL REGISTERED STUDENTS  (mass email)
     What it does: emails all students whose Status is Registered (all, or one state).
     Steps:
       1) In the Email panel, choose "Send to" (All / New Jersey / California).
       2) Type a Subject and the Message (basic HTML allowed; we add the greeting + sign-off).
       3) Click "Send email" and confirm.
       4) A toast reports how many were sent.
     Notes:
       - Goes only to Registered students (not Stand By or Cancelled).
       - Use it for confirmations, schedule/venue changes, reminders.
       - (SMS/text is a future option — currently email only.)

4.5  DOWNLOAD CSV / OPEN IN GOOGLE SHEETS  (export / share the list)
     - "⬇ Download CSV" downloads the CURRENT table view (respects your State/Status
       filters) — e.g. just "California + Registered". Opens in Excel/Sheets/Numbers.
     - "↗ Open in Google Sheets" opens the live Sheet in a new tab, where Google's own
       Share and File > Download (Excel/CSV/PDF) options live, and you can pick any tab.

4.6  REFRESH
     Click "↻ Refresh" to pull the latest numbers without reloading the page.

================================================================
5. MANAGING THE PROGRAM (the "Config" tab in the Sheet)
================================================================
Open the Sheet > "Config" tab. One row per state. Edit these cells (no code needed):
- Capacity : seat limit per state (e.g. 30). Drives Registered-vs-StandBy and Seats Left.
- RegOpen  : Yes/No. (The dashboard Open/Close buttons write this for you.)
- When / Where / Cost : shown on the public page (when a state is picked) and in emails.
Changes take effect immediately.
Important: raising Capacity does NOT auto-promote stand-by people — use "Promote next"
for each freed seat.

================================================================
6. MANAGING ADMINS (add or remove an admin)
================================================================
Admins are listed in the Sheet's "Admins" tab (one email per row). To ADD an admin:
   1) Add their Google email to the "Admins" tab.
   2) Share the Sheet with that email as Editor (Share button > add email > Editor).
      (Both are required: the list says "allowed", the share gives data access.)
To REMOVE an admin: delete their row from "Admins" (and optionally un-share the Sheet).
No code change or redeploy is needed for either.

================================================================
7. COMMON RECIPES (quick scenarios)
================================================================
- "A student dropped out, fill the seat" : Cancel their row (4.2) > Promote next (4.1).
- "Batch is full" : new sign-ups auto-go to Stand By; promote as seats free up.
- "Student made a typo" : edit their row directly in the Sheet (or ask them to reply
  to their confirmation email so you can fix it).
- "Student wants to cancel" : they contact you (reply to confirmation) > you Cancel (4.2).
- "Class is over for a location" : Close registration (4.3) for that state.
- "Announce a venue/time" : set When/Where in Config (5), then Mass email (4.4).

================================================================
8. UNDERSTANDING THE DATA (quick reference)
================================================================
Status values:
- Registered : confirmed, holds a seat.
- Stand By   : wait-listed (batch was full); has a "Standby Position" number.
- Cancelled  : withdrawn; frees a seat; kept for the record.
Duplicate rule: the same email cannot register twice for the SAME location (blocked
automatically). The same email CAN currently appear under both NJ and CA (separate
enrollments) — this is a pending policy decision.
Full field-by-field reference: the "Data Dictionary" (section 11).

================================================================
9. TROUBLESHOOTING
================================================================
- "Access denied" : wrong/!listed Google account, or not shared on the Sheet (see 2 & 6).
- "I made a change but don't see it" : click ↻ Refresh; if layout looks old, hard-refresh
  the browser (Ctrl/Cmd+Shift+R).
- "A student didn't get their email" : ask them to check spam; verify their email is
  spelled correctly in the Sheet; you can re-send via Mass email or by fixing + re-adding.
- "Counts look wrong" : the dashboard reads the Sheet live; check the Status column for
  the affected rows.
- (For whoever edits the code) Code/HTML edits only go live after Deploy > Manage
  deployments > Edit > New version > Deploy.

================================================================
10. GLOSSARY
================================================================
- Capacity   : the seat limit for a location (set in Config).
- Stand By   : the wait-list when a location is full.
- Promote    : move the next stand-by person into a freed seat.
- RegOpen    : whether a location is accepting sign-ups.
- Allowlist  : the "Admins" tab — who may use the dashboard.
- Config     : the Sheet tab holding capacity / open-close / dates per state.

================================================================
11. RESOURCE HUB (all related documents)
================================================================
- Sheet Data Dictionary (how the data is designed) :
  https://docs.google.com/spreadsheets/d/1tiOm6yPoxVAXl5s7t0-CN44bc0ITYN3oZxEUGAbKDjQ/edit
- Decision Register (open policy decisions) :
  https://docs.google.com/spreadsheets/d/1RwKBTw2Rb9KWqMY1uqrvw7tdPyr33Dyo2yCl4eRe87s/edit
- Migration Checklist (moving to a new host/domain) :
  https://docs.google.com/spreadsheets/d/1IH_21Ia55CDZ23LxBdLrbXIjzMrtGUGr7NPB1MIPOWQ/edit
- Deep-dive runbooks & briefs (in the project repo, ai-literacy-apps-script/docs/):
  Promote-Next how-to, Decision Brief, Migration Guide, Sheet design.
