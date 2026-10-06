-- cricstat reference data (F4, 2026-10-05). Loaded into the serving DB by every build, before core tables.
-- These rows ARE the cricket rules: change them here, never in code. Rationale: docs/F4-metric-dictionary.md.

-- Format mapping: every raw (match_type, team_type, balls_per_over) combination seen in Cricsheet.
-- A build fails if it meets a combination that is not listed (new formats must be classified on purpose).
INSERT INTO format_map (match_type, team_type, balls_per_over, format_key, format_family, level) VALUES
  ('Test', 'international', 6, 'TEST',          'multi_day', 'international_official'),
  ('ODI',  'international', 6, 'ODI',           'one_day',   'international_official'),
  ('T20',  'international', 6, 'T20I',          't20',       'international_official'),
  ('IT20', 'international', 6, 'T20I_OTHER',    't20',       'international_other'),
  ('ODM',  'international', 6, 'OD_INTL_OTHER', 'one_day',   'international_other'),
  ('MDM',  'international', 6, 'MD_INTL_OTHER', 'multi_day', 'international_other'),
  ('T20',  'club',          6, 'T20_LEAGUE',    't20',       'domestic'),
  ('T20',  'club',          5, 'HUNDRED',       'hundred',   'domestic'),
  ('ODM',  'club',          6, 'LIST_A',        'one_day',   'domestic'),
  ('MDM',  'club',          6, 'FIRST_CLASS',   'multi_day', 'domestic');

-- Phases (0-based over numbers). Fixed ranges by design: historical ODI powerplay rules varied, so ODI phases are
-- labelled by overs, not called "powerplay". Hundred "overs" are 5-ball sets: 25 / 50 / 25 balls.
INSERT INTO phase_defs (format_family, phase, from_over, to_over, label) VALUES
  ('t20',     'powerplay', 0,  5,  'Powerplay (overs 1–6)'),
  ('t20',     'middle',    6,  14, 'Middle (overs 7–15)'),
  ('t20',     'death',     15, 19, 'Death (overs 16–20)'),
  ('one_day', 'powerplay', 0,  9,  'Overs 1–10'),
  ('one_day', 'middle',    10, 39, 'Overs 11–40'),
  ('one_day', 'death',     40, 49, 'Overs 41–50'),
  ('hundred', 'powerplay', 0,  4,  'Powerplay (balls 1–25)'),
  ('hundred', 'middle',    5,  14, 'Middle (balls 26–75)'),
  ('hundred', 'death',     15, 19, 'Death (balls 76–100)');

-- Dismissal kinds: all 14 seen in the data.
--   counts_as_out      → ends the batting innings as "out" for averages (retired hurt / retired not out do not)
--   credited_to_bowler → counts in the bowler's wickets
INSERT INTO dismissal_kinds (kind, credited_to_bowler, counts_as_out) VALUES
  ('bowled', 1, 1), ('caught', 1, 1), ('caught and bowled', 1, 1), ('lbw', 1, 1), ('stumped', 1, 1), ('hit wicket', 1, 1),
  ('run out', 0, 1), ('obstructing the field', 0, 1), ('handled the ball', 0, 1), ('hit the ball twice', 0, 1),
  ('timed out', 0, 1), ('retired out', 0, 1),
  ('retired hurt', 0, 0), ('retired not out', 0, 0);

-- Featured leagues (F3 review decision 4, 2026-10-05): the "Leagues" tab, the LEAGUES / ALL scopes (F4 R21/R22)
-- and one player_career scope per slug. Keyed by Cricsheet's event name, so renamed events share a slug
-- (NatWest T20 Blast → Vitality Blast → Vitality Blast Men). Any other competition is added by the build
-- with is_featured = 0 and a slug made from its name.
INSERT INTO competitions (event_name, gender, team_type, competition_slug, is_featured) VALUES
  ('Indian Premier League',           'male',   'club', 'ipl',               1),
  ('Big Bash League',                 'male',   'club', 'bbl',               1),
  ('Pakistan Super League',           'male',   'club', 'psl',               1),
  ('Caribbean Premier League',        'male',   'club', 'cpl',               1),
  ('SA20',                            'male',   'club', 'sa20',              1),
  ('Major League Cricket',            'male',   'club', 'mlc',               1),
  ('NatWest T20 Blast',               'male',   'club', 't20-blast',         1),
  ('Vitality Blast',                  'male',   'club', 't20-blast',         1),
  ('Vitality Blast Men',              'male',   'club', 't20-blast',         1),
  ('The Hundred Men''s Competition',   'male',   'club', 'the-hundred-men',   1),
  ('Women''s Premier League',          'female', 'club', 'wpl',               1),
  ('Women''s Big Bash League',         'female', 'club', 'wbbl',              1),
  ('The Hundred Women''s Competition', 'female', 'club', 'the-hundred-women', 1);
