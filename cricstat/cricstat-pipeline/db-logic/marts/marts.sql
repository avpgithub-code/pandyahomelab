-- cricstat marts: player_career, player_year, player_teams, recomputed in full from the atoms on every
-- build (full or incremental). They store COUNTS only; every ratio lives in cricstat/sql/semantic_views.sql.
-- Rules applied here (docs/F4-metric-dictionary.md):
--   R7  super overs excluded (is_super_over = 0; fielding/phase atoms never hold super overs)
--   R13 matches with no ball bowled count for nobody (has_deliveries = 1); appearances = team sheet
--   R15 100s = 100+, 50s = 50–99, duck = 0 and out   R16 high score prefers not out on equal runs
--   R18 best bowling = most wickets, then fewest runs
--   R21/R22 scopes: every format_key; each featured competition slug; LEAGUES = featured domestic
--   leagues; ALL = official international formats + featured leagues (never other domestic cricket)

DROP TABLE IF EXISTS temp.match_scope;
CREATE TEMP TABLE match_scope (scope TEXT NOT NULL, match_key INTEGER NOT NULL,
  PRIMARY KEY (scope, match_key)) WITHOUT ROWID;
INSERT INTO match_scope
SELECT m.format_key, m.match_key FROM matches m WHERE m.has_deliveries = 1;
INSERT OR IGNORE INTO match_scope
SELECT c.competition_slug, m.match_key
FROM matches m JOIN competitions c USING (competition_key)
WHERE m.has_deliveries = 1 AND c.is_featured = 1;
INSERT INTO match_scope
SELECT 'LEAGUES', m.match_key
FROM matches m JOIN competitions c USING (competition_key)
JOIN format_map f ON f.match_type = m.match_type AND f.team_type = m.team_type
  AND f.balls_per_over = m.balls_per_over
WHERE m.has_deliveries = 1 AND c.is_featured = 1 AND f.level = 'domestic';
INSERT INTO match_scope
SELECT 'ALL', m.match_key
FROM matches m LEFT JOIN competitions c USING (competition_key)
JOIN format_map f ON f.match_type = m.match_type AND f.team_type = m.team_type
  AND f.balls_per_over = m.balls_per_over
WHERE m.has_deliveries = 1
  AND (f.level = 'international_official' OR (c.is_featured = 1 AND f.level = 'domestic'));

-- One gender per player: the gender of most of their matches. A handful of Cricsheet ids are shared by a
-- man and a woman (a Register merge, 10 ids on 2026-10-06); the build reports them as a warning.
DROP TABLE IF EXISTS temp.player_gender;
CREATE TEMP TABLE player_gender AS
SELECT player_key, gender FROM (
  SELECT mp.player_key, m.gender,
         ROW_NUMBER() OVER (PARTITION BY mp.player_key ORDER BY COUNT(*) DESC, m.gender) AS rn
  FROM match_players mp JOIN matches m USING (match_key)
  GROUP BY mp.player_key, m.gender)
WHERE rn = 1;

-- Appearances (team sheet) per player and scope.
DROP TABLE IF EXISTS temp.mart_app;
CREATE TEMP TABLE mart_app AS
SELECT s.scope, mp.player_key, g.gender, COUNT(*) AS matches,
       MIN(m.start_date) AS first_date, MAX(m.end_date) AS last_date
FROM match_players mp JOIN match_scope s USING (match_key) JOIN matches m USING (match_key)
JOIN player_gender g USING (player_key)
GROUP BY s.scope, mp.player_key, g.gender;

DROP TABLE IF EXISTS temp.mart_bat;
CREATE TEMP TABLE mart_bat AS
SELECT s.scope, b.player_key, COUNT(*) AS bat_innings, SUM(1 - b.is_out) AS not_outs,
       SUM(b.runs) AS runs, SUM(b.balls_faced) AS balls_faced,
       MAX(b.runs * 2 + (1 - b.is_out)) AS hs_code,          -- R16: runs, then not out
       SUM(b.runs >= 100) AS hundreds, SUM(b.runs BETWEEN 50 AND 99) AS fifties,
       SUM(b.runs = 0 AND b.is_out = 1) AS ducks, SUM(b.fours) AS fours, SUM(b.sixes) AS sixes
FROM batting_innings b JOIN match_scope s USING (match_key)
WHERE b.is_super_over = 0
GROUP BY s.scope, b.player_key;

DROP TABLE IF EXISTS temp.mart_bowl;
CREATE TEMP TABLE mart_bowl AS
SELECT s.scope, b.player_key, COUNT(*) AS bowl_innings, SUM(b.legal_balls) AS legal_balls,
       SUM(b.runs_conceded) AS runs_conceded, SUM(b.wickets) AS wickets, SUM(b.maidens) AS maidens,
       MAX(b.wickets * 100000 + (99999 - b.runs_conceded)) AS bb_code,   -- R18
       SUM(b.wickets = 4) AS four_wkt_hauls, SUM(b.wickets >= 5) AS five_wkt_hauls
FROM bowling_innings b JOIN match_scope s USING (match_key)
WHERE b.is_super_over = 0
GROUP BY s.scope, b.player_key;

DROP TABLE IF EXISTS temp.mart_fld;
CREATE TEMP TABLE mart_fld AS
SELECT s.scope, e.player_key, SUM(e.catches) AS catches, SUM(e.stumpings) AS stumpings,
       SUM(e.run_outs) AS run_outs
FROM fielding_events e JOIN match_scope s USING (match_key)
GROUP BY s.scope, e.player_key;

DELETE FROM player_career;
INSERT INTO player_career
SELECT a.player_key, a.scope, a.gender, a.matches,
       COALESCE(b.bat_innings, 0), COALESCE(b.not_outs, 0), COALESCE(b.runs, 0),
       COALESCE(b.balls_faced, 0), b.hs_code / 2, b.hs_code % 2,
       COALESCE(b.hundreds, 0), COALESCE(b.fifties, 0), COALESCE(b.ducks, 0),
       COALESCE(b.fours, 0), COALESCE(b.sixes, 0),
       COALESCE(w.bowl_innings, 0), COALESCE(w.legal_balls, 0), COALESCE(w.runs_conceded, 0),
       COALESCE(w.wickets, 0), COALESCE(w.maidens, 0),
       w.bb_code / 100000, 99999 - w.bb_code % 100000,
       COALESCE(w.four_wkt_hauls, 0), COALESCE(w.five_wkt_hauls, 0),
       COALESCE(f.catches, 0), COALESCE(f.stumpings, 0), COALESCE(f.run_outs, 0),
       a.first_date, a.last_date
FROM mart_app a
LEFT JOIN mart_bat b ON b.scope = a.scope AND b.player_key = a.player_key
LEFT JOIN mart_bowl w ON w.scope = a.scope AND w.player_key = a.player_key
LEFT JOIN mart_fld f ON f.scope = a.scope AND f.player_key = a.player_key;

-- Year by year (calendar year of the match start date).
DROP TABLE IF EXISTS temp.mart_year;
CREATE TEMP TABLE mart_year AS
SELECT s.scope, mp.player_key, CAST(substr(m.start_date, 1, 4) AS INTEGER) AS year,
       COUNT(*) AS matches
FROM match_players mp JOIN match_scope s USING (match_key) JOIN matches m USING (match_key)
GROUP BY 1, 2, 3;
DROP TABLE IF EXISTS temp.mart_year_bat;
CREATE TEMP TABLE mart_year_bat AS
SELECT s.scope, b.player_key, CAST(substr(b.start_date, 1, 4) AS INTEGER) AS year,
       SUM(b.runs) AS runs, COUNT(*) AS bat_innings, SUM(1 - b.is_out) AS not_outs,
       SUM(b.balls_faced) AS balls_faced
FROM batting_innings b JOIN match_scope s USING (match_key)
WHERE b.is_super_over = 0 GROUP BY 1, 2, 3;
DROP TABLE IF EXISTS temp.mart_year_bowl;
CREATE TEMP TABLE mart_year_bowl AS
SELECT s.scope, b.player_key, CAST(substr(b.start_date, 1, 4) AS INTEGER) AS year,
       SUM(b.wickets) AS wickets, SUM(b.legal_balls) AS legal_balls,
       SUM(b.runs_conceded) AS runs_conceded
FROM bowling_innings b JOIN match_scope s USING (match_key)
WHERE b.is_super_over = 0 GROUP BY 1, 2, 3;

DELETE FROM player_year;
INSERT INTO player_year
SELECT y.player_key, y.scope, y.year, y.matches,
       COALESCE(b.runs, 0), COALESCE(b.bat_innings, 0), COALESCE(b.not_outs, 0),
       COALESCE(b.balls_faced, 0), COALESCE(w.wickets, 0), COALESCE(w.legal_balls, 0),
       COALESCE(w.runs_conceded, 0)
FROM mart_year y
LEFT JOIN mart_year_bat b ON b.scope = y.scope AND b.player_key = y.player_key AND b.year = y.year
LEFT JOIN mart_year_bowl w ON w.scope = y.scope AND w.player_key = y.player_key AND w.year = y.year;

-- Who a player has represented (played matches only, R13).
DELETE FROM player_teams;
INSERT INTO player_teams
SELECT mp.player_key, mp.team_key, COUNT(*), MIN(m.start_date), MAX(m.end_date)
FROM match_players mp JOIN matches m USING (match_key)
WHERE m.has_deliveries = 1
GROUP BY mp.player_key, mp.team_key;

-- Batter v bowler (Head to Head matchups), official international formats only (decided 2026-10-26).
-- Balls = every delivery except wides (R3); runs off the bat; 4s/6s exclude non-boundary runs (R10);
-- dots = legal balls with no run off the bat; outs = the batter's dismissals credited to that bowler.
-- Every pair is kept (no minimum), so build_checks can prove the sums equal the batting atoms.
DROP TABLE IF EXISTS temp.mu_scope;
CREATE TEMP TABLE mu_scope (match_key INTEGER PRIMARY KEY, scope TEXT NOT NULL, start_date TEXT);
INSERT INTO mu_scope
SELECT match_key, format_key, start_date FROM matches
WHERE has_deliveries = 1 AND format_key IN ('TEST', 'ODI', 'T20I');

DROP TABLE IF EXISTS temp.mart_mu_outs;
CREATE TEMP TABLE mart_mu_outs AS
SELECT s.scope, x.player_out_key AS batter_key, x.bowler_key, x.kind, COUNT(*) AS n
FROM dismissals x JOIN mu_scope s USING (match_key)
JOIN innings i ON i.match_key = x.match_key AND i.innings_no = x.innings_no
WHERE i.is_super_over = 0 AND x.credited_to_bowler = 1 AND x.counts_as_out = 1
GROUP BY 1, 2, 3, 4;

DROP TABLE IF EXISTS temp.mart_mu;
CREATE TEMP TABLE mart_mu AS
SELECT s.scope, d.batter_key, d.bowler_key,
       SUM(d.wides = 0) AS balls, SUM(d.runs_batter) AS runs,
       SUM(d.is_legal = 1 AND d.runs_batter = 0) AS dots,
       SUM(d.runs_batter = 4 AND d.non_boundary = 0) AS fours,
       SUM(d.runs_batter = 6 AND d.non_boundary = 0) AS sixes,
       COUNT(DISTINCT d.match_key) AS matches, MIN(s.start_date) AS first_date,
       MAX(s.start_date) AS last_date
FROM deliveries d JOIN mu_scope s USING (match_key)
JOIN innings i ON i.match_key = d.match_key AND i.innings_no = d.innings_no
WHERE i.is_super_over = 0
GROUP BY 1, 2, 3;

DELETE FROM matchups;
INSERT INTO matchups (scope, batter_key, bowler_key, balls, runs, dots, fours, sixes, outs, matches,
                      first_date, last_date)
SELECT u.scope, u.batter_key, u.bowler_key, u.balls, u.runs, u.dots, u.fours, u.sixes,
       COALESCE(o.outs, 0), u.matches, u.first_date, u.last_date
FROM mart_mu u
LEFT JOIN (SELECT scope, batter_key, bowler_key, SUM(n) AS outs FROM mart_mu_outs GROUP BY 1, 2, 3) o
  ON o.scope = u.scope AND o.batter_key = u.batter_key AND o.bowler_key = u.bowler_key;
DELETE FROM matchup_outs;
INSERT INTO matchup_outs SELECT scope, batter_key, bowler_key, kind, n FROM mart_mu_outs;

DROP TABLE temp.mart_mu;
DROP TABLE temp.mart_mu_outs;
DROP TABLE temp.mu_scope;
DROP TABLE temp.mart_app;
DROP TABLE temp.mart_bat;
DROP TABLE temp.mart_bowl;
DROP TABLE temp.mart_fld;
DROP TABLE temp.mart_year;
DROP TABLE temp.mart_year_bat;
DROP TABLE temp.mart_year_bowl;
DROP TABLE temp.match_scope;
DROP TABLE temp.player_gender;
