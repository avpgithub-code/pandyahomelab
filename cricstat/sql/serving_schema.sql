-- cricstat serving database — DRAFT schema (F3, 2026-10-05). Not yet used by any code.
-- Built from data/db/raw.sqlite into a NEW file, quality-checked, then swapped in atomically.
-- Readers (cricstat-api, cricstat-agent) open it read-only, so journal_mode must stay DELETE.
-- Conventions: *_key = INTEGER surrogate (compact joins on 11.6M deliveries); natural ids kept alongside.
--   Over numbers are 0-based as in Cricsheet; phase boundaries live in phase_defs (data, not code).
--   Every metric formula is defined in F4; this file stores only the facts those formulas need.

PRAGMA journal_mode = DELETE;
PRAGMA foreign_keys = ON;

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, note TEXT);
CREATE TABLE build_info (                       -- one row per serving-DB build; drives "Data as of" on pages
  build_id INTEGER PRIMARY KEY, built_at TEXT NOT NULL, mode TEXT NOT NULL CHECK (mode IN ('full','incremental')),
  raw_run_id INTEGER, matches INTEGER, deliveries INTEGER, data_as_of TEXT, status TEXT NOT NULL, notes TEXT);

-- ───────────── Reference / dimension tables ─────────────
CREATE TABLE format_map (                       -- every raw combination → display format (see F3 §4)
  match_type TEXT NOT NULL, team_type TEXT NOT NULL, balls_per_over INTEGER NOT NULL,
  format_key TEXT NOT NULL,                     -- TEST, ODI, T20I, T20I_OTHER, OD_INTL_OTHER, MD_INTL_OTHER, T20_LEAGUE, HUNDRED, LIST_A, FIRST_CLASS
  format_family TEXT NOT NULL CHECK (format_family IN ('multi_day','one_day','t20','hundred')),
  level TEXT NOT NULL CHECK (level IN ('international_official','international_other','domestic')),
  PRIMARY KEY (match_type, team_type, balls_per_over));

CREATE TABLE phase_defs (                       -- limited-overs phases by format family (overs are 0-based;
  format_family TEXT NOT NULL, phase TEXT NOT NULL,   -- for the Hundred an "over" is a 5-ball set)
  from_over INTEGER NOT NULL, to_over INTEGER NOT NULL, label TEXT NOT NULL,
  PRIMARY KEY (format_family, phase));

CREATE TABLE competitions (
  competition_key INTEGER PRIMARY KEY, event_name TEXT NOT NULL, gender TEXT NOT NULL, team_type TEXT NOT NULL,
  competition_slug TEXT NOT NULL,               -- normalised name used in URLs and grouping (e.g. ipl)
  is_featured INTEGER NOT NULL DEFAULT 0,       -- IPL, BBL, PSL... shown under "Leagues"
  UNIQUE (event_name, gender, team_type));

CREATE TABLE teams (                            -- identity = name + gender + team_type ("India" men ≠ "India" women)
  team_key INTEGER PRIMARY KEY, name TEXT NOT NULL, gender TEXT NOT NULL, team_type TEXT NOT NULL,
  UNIQUE (name, gender, team_type));

CREATE TABLE venues (
  venue_key INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT,           -- city missing on 1,649 matches
  canonical_venue_key INTEGER REFERENCES venues(venue_key),             -- alias → canonical (manual map, later)
  country TEXT,                                                         -- needed for home/away; not in source (F3 open question)
  UNIQUE (name, city));

CREATE TABLE players (                          -- from Cricsheet Register people.csv; identifier is an 8-hex id
  player_key INTEGER PRIMARY KEY, player_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, unique_name TEXT NOT NULL);
CREATE TABLE player_external_ids (              -- long form of key_* columns; key_cricinfo has up to 3 per player
  player_key INTEGER NOT NULL REFERENCES players(player_key), source TEXT NOT NULL, external_id TEXT NOT NULL,
  PRIMARY KEY (player_key, source, external_id));
CREATE TABLE player_names (                     -- names.csv variants + derived aliases (surname, initials) for search
  player_key INTEGER NOT NULL REFERENCES players(player_key), name TEXT NOT NULL, source TEXT NOT NULL,
  PRIMARY KEY (player_key, name));
CREATE INDEX ix_player_names_name ON player_names(name COLLATE NOCASE);
CREATE TABLE player_bio (                       -- Wikidata enrichment; every column nullable (coverage is patchy)
  player_key INTEGER PRIMARY KEY REFERENCES players(player_key), wikidata_qid TEXT, date_of_birth TEXT,
  birthplace TEXT, country_for_sport TEXT, fetched_at TEXT,
  full_name TEXT,                                 -- Wikidata English label (CC0), e.g. "Smriti Mandhana"
  photo_file TEXT, photo_width INTEGER, photo_height INTEGER,   -- self-hosted thumbnail (data/photos/)
  photo_licence TEXT, photo_licence_url TEXT, photo_author TEXT, photo_source_url TEXT);
  -- Under-18s (on the build date) get no date_of_birth, birthplace or photo; sql/photo_blocklist.csv removes photos.

-- ───────────── Core facts (one row per real-world thing) ─────────────
CREATE TABLE matches (
  match_key INTEGER PRIMARY KEY, match_id TEXT NOT NULL UNIQUE,         -- TEXT: 25 ids are non-numeric (wi_*)
  match_type TEXT NOT NULL, team_type TEXT NOT NULL, gender TEXT NOT NULL, balls_per_over INTEGER NOT NULL,
  format_key TEXT NOT NULL, overs_limit INTEGER, match_type_number INTEGER,
  competition_key INTEGER REFERENCES competitions(competition_key), season TEXT NOT NULL,   -- season normalised to TEXT
  event_match_number INTEGER, event_stage TEXT, event_group TEXT,
  start_date TEXT NOT NULL, end_date TEXT NOT NULL, n_days INTEGER NOT NULL,
  venue_key INTEGER NOT NULL REFERENCES venues(venue_key),
  team1_key INTEGER NOT NULL REFERENCES teams(team_key), team2_key INTEGER NOT NULL REFERENCES teams(team_key),
  toss_winner_key INTEGER REFERENCES teams(team_key), toss_decision TEXT,
  result TEXT NOT NULL CHECK (result IN ('win','tie','draw','no_result')),
  winner_key INTEGER REFERENCES teams(team_key),                         -- also set for ties decided by eliminator/bowl-out
  win_by_runs INTEGER, win_by_wickets INTEGER, win_by_innings INTEGER,
  method TEXT,                                                           -- D/L, VJD, Awarded, Lost fewer wickets
  decided_by TEXT CHECK (decided_by IN ('play','super_over','bowl_out','award')),
  has_deliveries INTEGER NOT NULL,                                       -- 0 = abandoned/forfeited before a ball
  source_sha256 TEXT NOT NULL, source_revision INTEGER);
CREATE INDEX ix_matches_format_date ON matches(format_key, gender, start_date);
CREATE INDEX ix_matches_team1 ON matches(team1_key, start_date);
CREATE INDEX ix_matches_team2 ON matches(team2_key, start_date);
CREATE INDEX ix_matches_competition ON matches(competition_key, season);

CREATE TABLE match_players (                    -- team sheets: playing XI, supersubs, replacements that came in
  match_key INTEGER NOT NULL REFERENCES matches(match_key), team_key INTEGER NOT NULL REFERENCES teams(team_key),
  player_key INTEGER NOT NULL REFERENCES players(player_key),
  role TEXT NOT NULL CHECK (role IN ('xi','supersub','replacement')),
  PRIMARY KEY (match_key, player_key));
CREATE INDEX ix_match_players_player ON match_players(player_key);
CREATE TABLE player_of_match (match_key INTEGER NOT NULL REFERENCES matches(match_key),
  player_key INTEGER NOT NULL REFERENCES players(player_key), PRIMARY KEY (match_key, player_key));
CREATE TABLE match_officials (match_key INTEGER NOT NULL REFERENCES matches(match_key), role TEXT NOT NULL,
  name TEXT NOT NULL, PRIMARY KEY (match_key, role, name));

CREATE TABLE innings (
  match_key INTEGER NOT NULL REFERENCES matches(match_key), innings_no INTEGER NOT NULL,   -- 1-based, includes super overs
  batting_team_key INTEGER NOT NULL REFERENCES teams(team_key), bowling_team_key INTEGER NOT NULL REFERENCES teams(team_key),
  is_super_over INTEGER NOT NULL, declared INTEGER NOT NULL, forfeited INTEGER NOT NULL,
  target_runs INTEGER, target_overs REAL,                                 -- revised targets (D/L) arrive here
  penalty_runs_pre INTEGER NOT NULL DEFAULT 0, penalty_runs_post INTEGER NOT NULL DEFAULT 0,
  total_runs INTEGER NOT NULL, total_wickets INTEGER NOT NULL, legal_balls INTEGER NOT NULL,
  PRIMARY KEY (match_key, innings_no));
CREATE TABLE innings_absent_hurt (match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL,
  player_key INTEGER NOT NULL REFERENCES players(player_key), PRIMARY KEY (match_key, innings_no, player_key));
CREATE TABLE powerplays (match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, seq INTEGER NOT NULL,
  from_ball TEXT NOT NULL, to_ball TEXT NOT NULL, type TEXT NOT NULL, PRIMARY KEY (match_key, innings_no, seq));
CREATE TABLE miscounted_overs (match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, over_no INTEGER NOT NULL,
  balls INTEGER NOT NULL, PRIMARY KEY (match_key, innings_no, over_no));

CREATE TABLE deliveries (                       -- ~11.6M rows; grain = one ball bowled (legal or not)
  match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, over_no INTEGER NOT NULL, seq INTEGER NOT NULL, -- seq = order within the over, 1..n
  ball_label TEXT,                              -- Cricsheet actual_delivery, e.g. "0.1"
  batter_key INTEGER NOT NULL, non_striker_key INTEGER NOT NULL, bowler_key INTEGER NOT NULL,
  runs_batter INTEGER NOT NULL, runs_extras INTEGER NOT NULL, runs_total INTEGER NOT NULL,
  non_boundary INTEGER NOT NULL DEFAULT 0,      -- 4 or 6 runs that were NOT a boundary (all run / overthrows)
  wides INTEGER NOT NULL DEFAULT 0, noballs INTEGER NOT NULL DEFAULT 0, byes INTEGER NOT NULL DEFAULT 0,
  legbyes INTEGER NOT NULL DEFAULT 0, penalty INTEGER NOT NULL DEFAULT 0,
  is_legal INTEGER NOT NULL,                    -- 0 if wide or no-ball
  wickets INTEGER NOT NULL DEFAULT 0,           -- count; 16 deliveries have 2
  PRIMARY KEY (match_key, innings_no, over_no, seq)) WITHOUT ROWID;
CREATE INDEX ix_deliveries_batter ON deliveries(batter_key);
CREATE INDEX ix_deliveries_bowler ON deliveries(bowler_key);

CREATE TABLE dismissals (
  match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, over_no INTEGER NOT NULL, seq INTEGER NOT NULL,
  wicket_seq INTEGER NOT NULL, player_out_key INTEGER NOT NULL, kind TEXT NOT NULL,
  bowler_key INTEGER,                           -- bowler of that delivery
  credited_to_bowler INTEGER NOT NULL,          -- from dismissal_kinds; e.g. run out = 0
  counts_as_out INTEGER NOT NULL,               -- retired hurt / retired not out = 0 (F4 to confirm)
  PRIMARY KEY (match_key, innings_no, over_no, seq, wicket_seq));
CREATE INDEX ix_dismissals_player ON dismissals(player_out_key);
CREATE TABLE dismissal_fielders (
  match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, over_no INTEGER NOT NULL, seq INTEGER NOT NULL,
  wicket_seq INTEGER NOT NULL, fielder_seq INTEGER NOT NULL, player_key INTEGER, fielder_name TEXT NOT NULL,
  is_substitute INTEGER NOT NULL DEFAULT 0,     -- substitute fielders may not be in the registry → player_key NULL
  PRIMARY KEY (match_key, innings_no, over_no, seq, wicket_seq, fielder_seq));
CREATE INDEX ix_dismissal_fielders_player ON dismissal_fielders(player_key);
CREATE TABLE dismissal_kinds (                  -- reference data, reviewed in F4
  kind TEXT PRIMARY KEY, credited_to_bowler INTEGER NOT NULL, counts_as_out INTEGER NOT NULL);

CREATE TABLE reviews (                          -- DRS (17k deliveries); optional analytics
  match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, over_no INTEGER NOT NULL, seq INTEGER NOT NULL,
  by_team_key INTEGER, umpire TEXT, batter_key INTEGER, decision TEXT, umpires_call INTEGER, type TEXT,
  PRIMARY KEY (match_key, innings_no, over_no, seq));
CREATE TABLE replacements (                     -- impact players, concussion and injury replacements
  match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, over_no INTEGER NOT NULL, seq INTEGER NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('match','role')), team_key INTEGER, player_in_key INTEGER, player_out_key INTEGER,
  reason TEXT, role TEXT);

-- ───────────── Marts (rebuilt from core; what pages, the API and the agent read) ─────────────
-- Atoms: one row per player per innings. Almost every page and agent tool aggregates these.
CREATE TABLE batting_innings (
  match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, player_key INTEGER NOT NULL,
  team_key INTEGER NOT NULL, opponent_key INTEGER NOT NULL, format_key TEXT NOT NULL, gender TEXT NOT NULL,
  competition_key INTEGER, season TEXT NOT NULL, start_date TEXT NOT NULL, venue_key INTEGER NOT NULL,
  batting_position INTEGER, runs INTEGER NOT NULL, balls_faced INTEGER NOT NULL, fours INTEGER NOT NULL, sixes INTEGER NOT NULL,
  is_out INTEGER NOT NULL, dismissal_kind TEXT, is_super_over INTEGER NOT NULL,
  PRIMARY KEY (match_key, innings_no, player_key));
CREATE INDEX ix_bat_inn_player ON batting_innings(player_key, format_key);
CREATE TABLE bowling_innings (
  match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, player_key INTEGER NOT NULL,
  team_key INTEGER NOT NULL, opponent_key INTEGER NOT NULL, format_key TEXT NOT NULL, gender TEXT NOT NULL,
  competition_key INTEGER, season TEXT NOT NULL, start_date TEXT NOT NULL, venue_key INTEGER NOT NULL,
  legal_balls INTEGER NOT NULL, runs_conceded INTEGER NOT NULL, wickets INTEGER NOT NULL, maidens INTEGER NOT NULL,
  wides INTEGER NOT NULL, noballs INTEGER NOT NULL, dots INTEGER NOT NULL, is_super_over INTEGER NOT NULL,
  PRIMARY KEY (match_key, innings_no, player_key));
CREATE INDEX ix_bowl_inn_player ON bowling_innings(player_key, format_key);
CREATE TABLE fielding_events (
  match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, player_key INTEGER NOT NULL, format_key TEXT NOT NULL,
  catches INTEGER NOT NULL, stumpings INTEGER NOT NULL, run_outs INTEGER NOT NULL, as_substitute INTEGER NOT NULL,
  PRIMARY KEY (match_key, innings_no, player_key));
CREATE TABLE phase_stats (                      -- per player-innings-phase, limited-overs only
  match_key INTEGER NOT NULL, innings_no INTEGER NOT NULL, player_key INTEGER NOT NULL, phase TEXT NOT NULL,
  format_key TEXT NOT NULL, competition_key INTEGER, season TEXT NOT NULL,
  bat_runs INTEGER NOT NULL, bat_balls INTEGER NOT NULL, bat_outs INTEGER NOT NULL,
  bowl_balls INTEGER NOT NULL, bowl_runs INTEGER NOT NULL, bowl_wkts INTEGER NOT NULL,
  PRIMARY KEY (match_key, innings_no, player_key, phase));
CREATE INDEX ix_phase_player ON phase_stats(player_key, format_key, phase);

-- Page-level aggregates (small; pre-computed for speed — the API may also aggregate atoms directly)
CREATE TABLE player_career (                    -- Players page tables; scope = format_key or competition slug or 'ALL'
  player_key INTEGER NOT NULL, scope TEXT NOT NULL, gender TEXT NOT NULL,
  matches INTEGER NOT NULL, bat_innings INTEGER, not_outs INTEGER, runs INTEGER, balls_faced INTEGER, high_score INTEGER,
  high_score_not_out INTEGER, hundreds INTEGER, fifties INTEGER, ducks INTEGER, fours INTEGER, sixes INTEGER,
  bowl_innings INTEGER, legal_balls INTEGER, runs_conceded INTEGER, wickets INTEGER, maidens INTEGER,
  best_bowling_wkts INTEGER, best_bowling_runs INTEGER, four_wkt_hauls INTEGER, five_wkt_hauls INTEGER,
  catches INTEGER, stumpings INTEGER, run_outs INTEGER, first_date TEXT, last_date TEXT,
  PRIMARY KEY (player_key, scope));             -- averages / SR / economy are computed by F4 views, not stored
CREATE TABLE player_year (player_key INTEGER NOT NULL, scope TEXT NOT NULL, year INTEGER NOT NULL,
  matches INTEGER NOT NULL, runs INTEGER, bat_innings INTEGER, not_outs INTEGER, balls_faced INTEGER,
  wickets INTEGER, legal_balls INTEGER, runs_conceded INTEGER, PRIMARY KEY (player_key, scope, year));
CREATE TABLE player_teams (                     -- who a player has represented (players have no country field)
  player_key INTEGER NOT NULL, team_key INTEGER NOT NULL, matches INTEGER NOT NULL, first_date TEXT, last_date TEXT,
  PRIMARY KEY (player_key, team_key));

CREATE TABLE team_results (                     -- one row per team per match: base for records, H2H, form, Elo
  match_key INTEGER NOT NULL, team_key INTEGER NOT NULL, opponent_key INTEGER NOT NULL, format_key TEXT NOT NULL,
  gender TEXT NOT NULL, start_date TEXT NOT NULL, venue_key INTEGER NOT NULL, competition_key INTEGER,
  outcome TEXT NOT NULL CHECK (outcome IN ('won','lost','tied','drawn','no_result')),
  margin_runs INTEGER, margin_wickets INTEGER, home_away TEXT CHECK (home_away IN ('home','away','neutral')),
  PRIMARY KEY (match_key, team_key));
CREATE INDEX ix_team_results_team ON team_results(team_key, format_key, start_date);

-- Predictor (written by cricstat-models in P1; defined now so the API contract can reference it)
CREATE TABLE team_ratings (                     -- rating history after every rated match
  team_key INTEGER NOT NULL, format_key TEXT NOT NULL, as_of_date TEXT NOT NULL, match_key INTEGER,
  rating REAL NOT NULL, model_version TEXT NOT NULL, PRIMARY KEY (team_key, format_key, as_of_date, model_version));
CREATE TABLE forecast_runs (forecast_id INTEGER PRIMARY KEY, tournament TEXT NOT NULL, created_at TEXT NOT NULL,
  data_as_of TEXT NOT NULL, n_simulations INTEGER NOT NULL, model_version TEXT NOT NULL, mlflow_run_id TEXT);
CREATE TABLE forecast_team (forecast_id INTEGER NOT NULL REFERENCES forecast_runs(forecast_id),
  team_key INTEGER NOT NULL, stage TEXT NOT NULL, probability REAL NOT NULL, PRIMARY KEY (forecast_id, team_key, stage));

-- Semantic catalog: human/LLM descriptions of tables and columns (feeds the agent's schema prompt + Methodology page)
CREATE TABLE semantic_catalog (object_name TEXT NOT NULL, column_name TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL, PRIMARY KEY (object_name, column_name));
