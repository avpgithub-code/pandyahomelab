/**
 * AI Literacy Class — Registration backend (Google Apps Script Web App)
 * v2: per-state capacity + stand-by list + state-aware emails.
 *
 * Data model (all in the bound Google Sheet):
 *   - "Registrations" tab : one row per signup (see COLUMNS)
 *   - "Config" tab        : per-state Capacity / RegOpen / When / Where / Cost  (admin-editable)
 *   - "Dashboard" tab      : live per-state counts (formulas)
 *
 * Run setup() ONCE from the editor to build the tabs/columns.
 */

var SHEET_NAME      = 'Registrations';
var CONFIG_SHEET    = 'Config';
var DASHBOARD_SHEET = 'Dashboard';

var NOTIFY_EMAIL = 'architpandya@yahoo.com';
var FROM_NAME    = 'pandyaHomeLab · AI Literacy Class';

var STATES = ['New Jersey', 'California'];

var COLUMNS = [
  'Timestamp', 'State', 'Status', 'Standby Position',
  'First', 'Last', 'Email', 'Phone', 'AI Level', 'How Heard',
  'Prereq: Claude', 'Prereq: Basic skills',
  'Notes', 'SMS Consent', 'Marketing Opt-in'
];

/* ----------------------------------------------------------------------
 * SETUP — run once from the editor (Run ▶ setup). Safe to re-run.
 * -------------------------------------------------------------------- */
function setup() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // Registrations tab: write the v2 header row.
  var reg = ss.getSheetByName(SHEET_NAME) || ss.getSheets()[0];
  reg.setName(SHEET_NAME);
  reg.getRange(1, 1, 1, reg.getMaxColumns()).clearContent(); // drop stale headers (e.g. removed columns)
  reg.getRange(1, 1, 1, COLUMNS.length).setValues([COLUMNS]).setFontWeight('bold');
  reg.setFrozenRows(1);

  // Config tab: per-state settings (only seeded if empty, so admin edits stick).
  var cfg = ss.getSheetByName(CONFIG_SHEET) || ss.insertSheet(CONFIG_SHEET);
  if (cfg.getLastRow() === 0) {
    cfg.getRange(1, 1, 1, 6)
       .setValues([['State', 'Capacity', 'RegOpen', 'When', 'Where', 'Cost']])
       .setFontWeight('bold');
    cfg.getRange(2, 1, 2, 6).setValues([
      ['New Jersey', 30, 'Yes', 'To be announced', 'To be announced', 'To be announced'],
      ['California', 30, 'Yes', 'To be announced', 'To be announced', 'To be announced']
    ]);
    cfg.setFrozenRows(1);
  }

  // Dashboard tab: live counts via formulas.
  var dash = ss.getSheetByName(DASHBOARD_SHEET) || ss.insertSheet(DASHBOARD_SHEET);
  dash.clear();
  dash.getRange(1, 1).setValue('AI Literacy — Live Dashboard').setFontWeight('bold');
  dash.getRange(3, 1, 1, 6)
      .setValues([['State', 'Capacity', 'Registered', 'Stand By', 'Seats Left', 'RegOpen']])
      .setFontWeight('bold');

  var rows = [];
  for (var i = 0; i < STATES.length; i++) {
    var s = STATES[i], r = 4 + i;
    rows.push([
      s,
      '=IFERROR(VLOOKUP("' + s + '",' + CONFIG_SHEET + '!A:B,2,FALSE),0)',
      '=COUNTIFS(' + SHEET_NAME + '!B:B,"' + s + '",' + SHEET_NAME + '!C:C,"Registered")',
      '=COUNTIFS(' + SHEET_NAME + '!B:B,"' + s + '",' + SHEET_NAME + '!C:C,"Stand By")',
      '=B' + r + '-C' + r,
      '=IFERROR(VLOOKUP("' + s + '",' + CONFIG_SHEET + '!A:C,3,FALSE),"")'
    ]);
  }
  dash.getRange(4, 1, rows.length, 6).setValues(rows);

  var tr = 4 + STATES.length;
  dash.getRange(tr, 1, 1, 6).setValues([['TOTAL',
    '=SUM(B4:B' + (tr - 1) + ')', '=SUM(C4:C' + (tr - 1) + ')',
    '=SUM(D4:D' + (tr - 1) + ')', '=SUM(E4:E' + (tr - 1) + ')', '']]);
  dash.getRange(tr, 1, 1, 6).setFontWeight('bold');
}

/* ----------------------------------------------------------------------
 * POST — a registration submission.
 * -------------------------------------------------------------------- */
function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000); // serialize so two people can't grab the last seat

    var data = parseBody_(e);

    if (data._gotcha) return json_({ ok: true, status: 'registered' }); // bot: silently drop

    var required = ['first', 'last', 'email', 'level', 'state'];
    for (var i = 0; i < required.length; i++) {
      if (!data[required[i]]) return json_({ ok: false, error: 'Missing field: ' + required[i] });
    }
    if (STATES.indexOf(String(data.state)) === -1) return json_({ ok: false, error: 'Invalid state' });
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(data.email))) return json_({ ok: false, error: 'Invalid email' });

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME) || ss.getSheets()[0];
    var values = sheet.getDataRange().getValues();
    var h = values[0];
    var si = h.indexOf('State'), ti = h.indexOf('Status'), ei = h.indexOf('Email');

    var state = String(data.state);
    var emailLc = String(data.email).toLowerCase();

    // De-dup: same email + state, not cancelled → don't consume a second seat.
    for (var r = 1; r < values.length; r++) {
      if (String(values[r][si]) === state &&
          String(values[r][ei]).toLowerCase() === emailLc &&
          String(values[r][ti]) !== 'Cancelled') {
        return json_({ ok: true, status: 'duplicate', state: state });
      }
    }

    var cfg = readConfig_()[state] || {};
    if (!isOpen_(cfg.regOpen)) return json_({ ok: true, status: 'closed', state: state });

    var capacity = Number(cfg.capacity) || 0;
    var registered = 0, standby = 0;
    for (var r2 = 1; r2 < values.length; r2++) {
      if (String(values[r2][si]) === state) {
        var st = String(values[r2][ti]);
        if (st === 'Registered') registered++;
        else if (st === 'Stand By') standby++;
      }
    }

    var status, position = '';
    if (registered < capacity) {
      status = 'Registered';
    } else {
      status = 'Stand By';
      position = standby + 1;
    }

    sheet.appendRow(buildRow_(h, data, state, status, position));

    // Best-effort: registration is already saved, so email failure must not error the visitor.
    try { sendEmails_(data, state, status, position, cfg); } catch (mailErr) {}

    return json_({
      ok: true,
      status: status === 'Registered' ? 'registered' : 'standby',
      position: position,
      state: state
    });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

/* ----------------------------------------------------------------------
 * GET — public per-state config + seat availability (for the page).
 * -------------------------------------------------------------------- */
function doGet() {
  try {
    var cfg = readConfig_();
    var counts = countByState_();
    var out = [];
    for (var i = 0; i < STATES.length; i++) {
      var s = STATES[i], c = cfg[s] || {};
      var cap = Number(c.capacity) || 0;
      var reg = (counts[s] && counts[s].registered) || 0;
      out.push({
        state: s,
        regOpen: isOpen_(c.regOpen),
        when: c.when || 'To be announced',
        where: c.where || 'To be announced',
        cost: c.cost || 'To be announced',
        capacity: cap,
        registered: reg,
        seatsLeft: Math.max(0, cap - reg),
        full: reg >= cap
      });
    }
    return json_({ ok: true, states: out });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

/* ----------------------------- helpers ------------------------------ */

function readConfig_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cfg = ss.getSheetByName(CONFIG_SHEET);
  var map = {};
  if (!cfg) return map;
  var vals = cfg.getDataRange().getValues();
  for (var r = 1; r < vals.length; r++) {
    if (!vals[r][0]) continue;
    map[String(vals[r][0])] = {
      capacity: vals[r][1], regOpen: vals[r][2],
      when: vals[r][3], where: vals[r][4], cost: vals[r][5]
    };
  }
  return map;
}

function countByState_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME) || ss.getSheets()[0];
  var vals = sheet.getDataRange().getValues();
  var h = vals[0], si = h.indexOf('State'), ti = h.indexOf('Status');
  var out = {};
  for (var r = 1; r < vals.length; r++) {
    var s = String(vals[r][si]); if (!s) continue;
    if (!out[s]) out[s] = { registered: 0, standby: 0 };
    var st = String(vals[r][ti]);
    if (st === 'Registered') out[s].registered++;
    else if (st === 'Stand By') out[s].standby++;
  }
  return out;
}

function isOpen_(v) {
  return v === true || String(v).toLowerCase() === 'yes' || String(v).toLowerCase() === 'true';
}

function buildRow_(h, data, state, status, position) {
  var map = {
    'Timestamp': new Date(), 'State': state, 'Status': status, 'Standby Position': position,
    'First': safe_(data.first), 'Last': safe_(data.last), 'Email': safe_(data.email),
    'Phone': safe_(data.phone), 'AI Level': safe_(data.level), 'How Heard': safe_(data.hear),
    'Prereq: Claude': data.p1 ? 'Yes' : 'No',
    'Prereq: Basic skills': data.p3 ? 'Yes' : 'No', 'Notes': safe_(data.notes),
    'SMS Consent': data.smsconsent ? 'Yes' : 'No', 'Marketing Opt-in': data.updates ? 'Yes' : 'No'
  };
  var row = [];
  for (var i = 0; i < h.length; i++) row.push(map.hasOwnProperty(h[i]) ? map[h[i]] : '');
  return row;
}

function sendEmails_(data, state, status, position, cfg) {
  var name = ((data.first || '') + ' ' + (data.last || '')).trim() || 'there';
  var details = cfg ?
    "<p><b>" + escapeHtml_(state) + " session</b><br>" +
    "When: " + escapeHtml_(cfg.when || 'To be announced') + "<br>" +
    "Where: " + escapeHtml_(cfg.where || 'To be announced') + "<br>" +
    "Cost: " + escapeHtml_(cfg.cost || 'To be announced') + "</p>" : "";

  if (data.email) {
    if (status === 'Registered') {
      MailApp.sendEmail({
        to: String(data.email), name: FROM_NAME,
        subject: "You're registered — AI Literacy Class (" + state + ")",
        htmlBody:
          "<p>Hi " + escapeHtml_(name) + ",</p>" +
          "<p>You're registered for the <b>AI Literacy Class — " + escapeHtml_(state) + "</b>! 🎉</p>" +
          details +
          "<p>Please come prepared with a paid Claude account and basic computer skills. " +
          "We'll email the final joining details before the session.</p>" +
          "<p>See you soon,<br>The pandyaHomeLab team</p>"
      });
    } else {
      MailApp.sendEmail({
        to: String(data.email), name: FROM_NAME,
        subject: "You're on the stand-by list — AI Literacy Class (" + state + ")",
        htmlBody:
          "<p>Hi " + escapeHtml_(name) + ",</p>" +
          "<p>Thanks for your interest in the <b>AI Literacy Class — " + escapeHtml_(state) + "</b>. " +
          "This batch is currently <b>full</b>, so we've added you to the <b>stand-by list</b>" +
          (position ? " — you're <b>#" + position + "</b>" : "") + ".</p>" +
          "<p>If someone cancels, we offer spots on a first-come basis and will email you right away.</p>" +
          "<p>The pandyaHomeLab team</p>"
      });
    }
  }

  if (NOTIFY_EMAIL) {
    var opts = {
      to: NOTIFY_EMAIL, name: FROM_NAME,
      subject: "New " + (status === 'Registered' ? 'registration' : 'stand-by') + " (" + state + "): " + name,
      htmlBody:
        "<p>New <b>" + escapeHtml_(status) + "</b> — " + escapeHtml_(state) +
        (position ? " (stand-by #" + position + ")" : "") + "</p><ul>" +
        "<li><b>Name:</b> " + escapeHtml_(name) + "</li>" +
        "<li><b>Email:</b> " + escapeHtml_(data.email || '') + "</li>" +
        "<li><b>Phone:</b> " + escapeHtml_(data.phone || '') + "</li>" +
        "<li><b>AI experience:</b> " + escapeHtml_(data.level || '') + "</li>" +
        "<li><b>Heard via:</b> " + escapeHtml_(data.hear || '') + "</li>" +
        "<li><b>Notes:</b> " + escapeHtml_(data.notes || '') + "</li></ul>"
    };
    if (data.email) opts.replyTo = String(data.email);
    MailApp.sendEmail(opts);
  }
}

/** Run once from the editor to authorise email sending + verify it works. */
function testEmail() {
  var cfg = readConfig_()['New Jersey'] || {};
  sendEmails_({
    first: 'Test', last: 'Run', email: NOTIFY_EMAIL, phone: '+1 555 000 0000',
    level: 'Complete beginner', hear: 'Email', notes: 'authorization test', updates: true
  }, 'New Jersey', 'Registered', '', cfg);
}

function safe_(v) {
  v = (v == null) ? '' : String(v);
  return /^[=+\-@\t\r\n]/.test(v) ? "'" + v : v;
}

function escapeHtml_(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function parseBody_(e) {
  if (e && e.postData && e.postData.contents) {
    try { return JSON.parse(e.postData.contents); } catch (ignore) {}
  }
  return (e && e.parameter) ? e.parameter : {};
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
