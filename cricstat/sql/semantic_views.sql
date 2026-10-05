-- cricstat semantic views (F4, 2026-10-05): the ONLY place derived ratios are defined.
-- Pages, cricstat-api and the agent read these views; nothing else recomputes an average or an economy.
-- Inputs are the count columns built from deliveries by the build step (rules in docs/F4-metric-dictionary.md).
-- Division by zero yields NULL, shown as "—". Rounding is left to the presentation layer.

CREATE VIEW v_player_batting AS
SELECT p.player_key, p.player_id, p.name, c.scope, c.gender, c.matches,
       c.bat_innings AS innings, c.not_outs, c.runs, c.balls_faced,
       c.high_score, c.high_score_not_out,
       c.runs * 1.0 / NULLIF(c.bat_innings - c.not_outs, 0) AS average,      -- runs ÷ dismissals
       c.runs * 100.0 / NULLIF(c.balls_faced, 0) AS strike_rate,             -- runs per 100 balls faced
       c.hundreds, c.fifties, c.ducks, c.fours, c.sixes, c.first_date, c.last_date
FROM player_career c JOIN players p USING (player_key)
WHERE c.bat_innings > 0;

CREATE VIEW v_player_bowling AS
SELECT p.player_key, p.player_id, p.name, c.scope, c.gender, c.matches,
       c.bowl_innings AS innings, c.legal_balls,
       (c.legal_balls / 6) || '.' || (c.legal_balls % 6) AS overs_display,   -- 6-ball notation, e.g. 47.3
       c.maidens, c.runs_conceded, c.wickets,
       c.runs_conceded * 1.0 / NULLIF(c.wickets, 0) AS average,              -- runs conceded ÷ wickets
       c.runs_conceded * 6.0 / NULLIF(c.legal_balls, 0) AS economy,          -- per 6 legal balls (incl. the Hundred)
       c.legal_balls * 1.0 / NULLIF(c.wickets, 0) AS strike_rate,            -- balls per wicket
       c.best_bowling_wkts, c.best_bowling_runs, c.four_wkt_hauls, c.five_wkt_hauls
FROM player_career c JOIN players p USING (player_key)
WHERE c.bowl_innings > 0;

CREATE VIEW v_player_fielding AS
SELECT p.player_key, p.player_id, p.name, c.scope, c.gender, c.matches,
       c.catches, c.stumpings, c.run_outs, c.catches + c.stumpings AS dismissals
FROM player_career c JOIN players p USING (player_key);

CREATE VIEW v_player_phase AS                                -- limited-overs phase splits per player
SELECT s.player_key, s.format_key, s.phase, d.label AS phase_label,
       SUM(s.bat_runs) AS bat_runs, SUM(s.bat_balls) AS bat_balls, SUM(s.bat_outs) AS bat_outs,
       SUM(s.bat_runs) * 100.0 / NULLIF(SUM(s.bat_balls), 0) AS bat_strike_rate,
       SUM(s.bowl_balls) AS bowl_balls, SUM(s.bowl_runs) AS bowl_runs, SUM(s.bowl_wkts) AS bowl_wkts,
       SUM(s.bowl_runs) * 6.0 / NULLIF(SUM(s.bowl_balls), 0) AS bowl_economy
FROM phase_stats s
JOIN format_map f ON f.format_key = s.format_key
JOIN phase_defs d ON d.format_family = f.format_family AND d.phase = s.phase
GROUP BY s.player_key, s.format_key, s.phase, d.label;

CREATE VIEW v_team_record AS                                 -- Countries page "Record by format"
SELECT r.team_key, t.name AS team, r.gender, r.format_key,
       COUNT(*) AS matches,
       SUM(r.outcome = 'won') AS won, SUM(r.outcome = 'lost') AS lost, SUM(r.outcome = 'tied') AS tied,
       SUM(r.outcome = 'drawn') AS drawn, SUM(r.outcome = 'no_result') AS no_result,
       SUM(r.outcome = 'won') * 100.0 / NULLIF(COUNT(*) - SUM(r.outcome = 'no_result'), 0) AS win_pct
FROM team_results r JOIN teams t USING (team_key)
GROUP BY r.team_key, t.name, r.gender, r.format_key;

CREATE VIEW v_head_to_head AS                                -- Countries page "Head to head"
SELECT r.team_key, r.opponent_key, o.name AS opponent, r.format_key,
       COUNT(*) AS matches, SUM(r.outcome = 'won') AS won, SUM(r.outcome = 'lost') AS lost,
       SUM(r.outcome = 'won') * 100.0 / NULLIF(COUNT(*) - SUM(r.outcome = 'no_result'), 0) AS win_pct,
       MAX(r.start_date) AS last_played
FROM team_results r JOIN teams o ON o.team_key = r.opponent_key
GROUP BY r.team_key, r.opponent_key, o.name, r.format_key;
