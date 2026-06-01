/**
 * AI Literacy Class — ADMIN dashboard (standalone Apps Script web app).
 *
 * This is a SEPARATE project from the public registration backend. It reads
 * the same Google Sheet by ID. Deploy it as a web app with:
 *     Execute as:        Me
 *     Who has access:    Only myself   (add specific Google accounts later for team admins)
 * That Google-login restriction is the security boundary.
 *
 * Files in this project:
 *   - Code.gs  (this file)
 *   - Index    (HTML — the dashboard UI)
 */

var SHEET_ID     = '1NFz4Y-qoA-kUnmJuiS4i7xlP6B8EgXmVbp_P7WbRtjo';
var SHEET_NAME   = 'Registrations';
var CONFIG_SHEET = 'Config';
var FROM_NAME    = 'pandyaHomeLab · AI Literacy Class';
var STATES       = ['New Jersey', 'California'];

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('AI Literacy — Admin')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function ss_() { return SpreadsheetApp.openById(SHEET_ID); }

/* ---------------------------------- read --------------------------------- */
function getData() {
  var ss = ss_();
  var reg = ss.getSheetByName(SHEET_NAME);
  var vals = reg.getDataRange().getValues();
  var h = vals[0];
  var idx = {};
  for (var i = 0; i < h.length; i++) idx[h[i]] = i;

  var cfg = readConfig_();
  var tz = Session.getScriptTimeZone();

  var regs = [];
  for (var r = 1; r < vals.length; r++) {
    var row = vals[r];
    if (!row[idx['Email']] && !row[idx['First']]) continue;
    regs.push({
      row: r + 1,
      timestamp: row[idx['Timestamp']] ? Utilities.formatDate(new Date(row[idx['Timestamp']]), tz, 'yyyy-MM-dd HH:mm') : '',
      state: row[idx['State']], status: row[idx['Status']], position: row[idx['Standby Position']],
      first: row[idx['First']], last: row[idx['Last']], email: row[idx['Email']],
      phone: row[idx['Phone']], level: row[idx['AI Level']], hear: row[idx['How Heard']], notes: row[idx['Notes']]
    });
  }

  var summary = [];
  for (var s = 0; s < STATES.length; s++) {
    var state = STATES[s], c = cfg[state] || {};
    var cap = Number(c.capacity) || 0;
    var registered = regs.filter(function (x) { return x.state === state && x.status === 'Registered'; }).length;
    var standby = regs.filter(function (x) { return x.state === state && x.status === 'Stand By'; }).length;
    summary.push({
      state: state, capacity: cap, registered: registered, standby: standby,
      seatsLeft: Math.max(0, cap - registered), pctFull: cap ? Math.round(registered / cap * 100) : 0,
      regOpen: isOpen_(c.regOpen)
    });
  }

  regs.reverse(); // newest first
  return {
    admin: getActiveEmail_(),
    generatedAt: Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd HH:mm'),
    summary: summary, registrations: regs
  };
}

/* --------------------------------- actions ------------------------------- */

// Mark a registration as Cancelled (frees a seat for promotion).
function markCancelled(rowNumber) {
  var lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    var reg = ss_().getSheetByName(SHEET_NAME);
    var h = reg.getRange(1, 1, 1, reg.getLastColumn()).getValues()[0];
    reg.getRange(rowNumber, h.indexOf('Status') + 1).setValue('Cancelled');
    reg.getRange(rowNumber, h.indexOf('Standby Position') + 1).setValue('');
    return { message: 'Registration cancelled.', data: getData() };
  } finally { lock.releaseLock(); }
}

// Promote the earliest stand-by for a state → Registered, email them, renumber the rest.
function promoteNext(state) {
  var lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    var reg = ss_().getSheetByName(SHEET_NAME);
    var vals = reg.getDataRange().getValues();
    var h = vals[0];
    var iState = h.indexOf('State'), iStatus = h.indexOf('Status'), iPos = h.indexOf('Standby Position'),
        iEmail = h.indexOf('Email'), iFirst = h.indexOf('First'), iLast = h.indexOf('Last'), iTime = h.indexOf('Timestamp');

    var standbys = [];
    for (var r = 1; r < vals.length; r++) {
      if (String(vals[r][iState]) === state && String(vals[r][iStatus]) === 'Stand By') {
        standbys.push({ rowNum: r + 1, pos: Number(vals[r][iPos]) || 9999, time: vals[r][iTime],
          first: vals[r][iFirst], last: vals[r][iLast], email: vals[r][iEmail] });
      }
    }
    if (!standbys.length) return { message: 'No one is on the stand-by list for ' + state + '.', data: getData() };

    standbys.sort(function (a, b) { return a.pos - b.pos || (new Date(a.time)) - (new Date(b.time)); });

    var p = standbys[0];
    reg.getRange(p.rowNum, iStatus + 1).setValue('Registered');
    reg.getRange(p.rowNum, iPos + 1).setValue('');
    for (var k = 1; k < standbys.length; k++) reg.getRange(standbys[k].rowNum, iPos + 1).setValue(k); // renumber

    try { sendPromotionEmail_(p, state, readConfig_()[state] || {}); } catch (e) {}

    var name = ((p.first || '') + ' ' + (p.last || '')).trim() || p.email;
    return { message: 'Promoted ' + name + ' to Registered (emailed).', data: getData() };
  } finally { lock.releaseLock(); }
}

// Open or close registration for a state (writes Config!RegOpen).
function setRegOpen(state, open) {
  var lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    var cfg = ss_().getSheetByName(CONFIG_SHEET);
    var vals = cfg.getDataRange().getValues();
    var h = vals[0];
    var iState = h.indexOf('State'), iOpen = h.indexOf('RegOpen');
    for (var r = 1; r < vals.length; r++) {
      if (String(vals[r][iState]) === state) {
        cfg.getRange(r + 1, iOpen + 1).setValue(open ? 'Yes' : 'No');
        return { message: 'Registration ' + (open ? 'OPENED' : 'CLOSED') + ' for ' + state + '.', data: getData() };
      }
    }
    return { message: 'State not found: ' + state, data: getData() };
  } finally { lock.releaseLock(); }
}

// Email all Registered students in a scope ('all' | state name).
function sendMassEmail(scope, subject, bodyHtml) {
  if (!subject || !bodyHtml) return { message: 'Subject and message are both required.', data: getData() };
  var data = getData();
  var sent = 0;
  data.registrations.forEach(function (x) {
    if (x.status === 'Registered' && x.email && (scope === 'all' || x.state === scope)) {
      try {
        MailApp.sendEmail({
          to: String(x.email), name: FROM_NAME, subject: subject,
          htmlBody: '<p>Hi ' + esc_(x.first || 'there') + ',</p>' + bodyHtml + '<p>— The pandyaHomeLab team</p>'
        });
        sent++;
      } catch (e) {}
    }
  });
  return { message: 'Sent to ' + sent + ' registered student(s)' + (scope === 'all' ? '' : ' in ' + scope) + '.', data: getData() };
}

/* --------------------------------- helpers ------------------------------- */
function sendPromotionEmail_(p, state, cfg) {
  if (!p.email) return;
  var name = ((p.first || '') + ' ' + (p.last || '')).trim() || 'there';
  var details = cfg ?
    '<p><b>' + esc_(state) + ' session</b><br>When: ' + esc_(cfg.when || 'To be announced') +
    '<br>Where: ' + esc_(cfg.where || 'To be announced') + '<br>Cost: ' + esc_(cfg.cost || 'To be announced') + '</p>' : '';
  MailApp.sendEmail({
    to: String(p.email), name: FROM_NAME,
    subject: "Good news — a spot opened up! AI Literacy Class (" + state + ")",
    htmlBody: '<p>Hi ' + esc_(name) + ',</p>' +
      '<p>A spot has opened in the <b>AI Literacy Class — ' + esc_(state) + '</b> and you’re in! 🎉 ' +
      'You’ve been moved from the stand-by list to <b>registered</b>.</p>' + details +
      '<p>Please come prepared with a paid Claude account and basic computer skills. ' +
      'See you soon,<br>The pandyaHomeLab team</p>'
  });
}

function readConfig_() {
  var cfg = ss_().getSheetByName(CONFIG_SHEET);
  var map = {};
  if (!cfg) return map;
  var vals = cfg.getDataRange().getValues();
  for (var r = 1; r < vals.length; r++) {
    if (!vals[r][0]) continue;
    map[String(vals[r][0])] = { capacity: vals[r][1], regOpen: vals[r][2], when: vals[r][3], where: vals[r][4], cost: vals[r][5] };
  }
  return map;
}

function isOpen_(v) { return v === true || String(v).toLowerCase() === 'yes' || String(v).toLowerCase() === 'true'; }
function getActiveEmail_() { try { return Session.getActiveUser().getEmail() || Session.getEffectiveUser().getEmail(); } catch (e) { return ''; } }
function esc_(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
