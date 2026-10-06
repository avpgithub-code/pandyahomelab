# F4 — cricstat metric dictionary

Status: **approved** (2026-10-05). It settles the 9 traps listed in F3 §11.
Where the rules live:

| File | What it holds |
|---|---|
| [`../sql/reference_data.sql`](../sql/reference_data.sql) | The rules as data: format map, phases, dismissal kinds |
| [`../sql/semantic_views.sql`](../sql/semantic_views.sql) | The **only** place ratios are defined |
| [`../cricstat-pipeline/tests/fixtures/f4_metric_cases.json`](../cricstat-pipeline/tests/fixtures/f4_metric_cases.json) | 13 hand-built cases with expected counts |
| [`../cricstat-pipeline/tests/sql/test_semantic_views.py`](../cricstat-pipeline/tests/sql/test_semantic_views.py) | 10 passing tests |

**Principle:** the build step stores **counts** and the views compute **ratios**. A rule change is an edit to
`reference_data.sql` or one view. It is never a code change in several places.

The conventions follow standard scoring practice: the Laws of Cricket and the usual scorecard conventions used by
statisticians. The Laws are referenced, not reproduced. Where practice varies, the choice is stated and shown on the
Methodology page.

## 1. Rules
| # | Rule | Decision | Case |
|---|---|---|---|
| R1 | Is the batter out? | Out for averages: bowled, caught, caught and bowled, lbw, stumped, hit wicket, run out, obstructing the field, handled the ball, hit the ball twice, timed out, retired out. **Not out:** retired hurt, retired not out | C4 |
| R2 | Bowler's wicket? | Credited: bowled, caught, caught and bowled, lbw, stumped, hit wicket. **Not credited:** run out, obstructing the field, handled the ball, hit the ball twice, timed out and all retirements | C4, C5 |
| R3 | Balls faced | Every delivery received **except wides**. No-balls count as balls faced | C1 |
| R4 | Runs conceded by the bowler | `runs_batter + wides + noballs` (all wide and no-ball runs). **Byes, leg-byes and penalty runs are not charged.** Penalty runs count to the team total only | C1, C9 |
| R5 | Bowler's legal balls | Deliveries that are neither a wide nor a no-ball. Shown as overs in 6-ball notation (37.3) | C1 |
| R6 | Maiden | One bowler bowls the **whole over** and concedes 0 (byes and leg-byes allowed). A shared over is no one's maiden. Miscounted overs follow the same rule. **There are no maidens in the Hundred** (5-ball sets) | C2, C3, C8 |
| R7 | Super overs | Excluded from every player career stat and from innings totals used in records. The match result records how a tie was decided | C7 |
| R8 | Dot ball (bowler) | A legal ball with 0 runs conceded by the bowler (a bye or leg-bye ball is a dot for the bowler) | C1, C2 |
| R9 | The Hundred | Economy is **per 6 legal balls**, like every other format, so economies compare across formats. Phases are by 5-ball set: balls 1–25, 26–75, 76–100 | C8 |
| R10 | Fours and sixes | `runs_batter` = 4 or 6 **and not** `non_boundary`. A boundary off a no-ball counts | C1, C9 |
| R11 | Batting innings | A player has an innings if they faced a ball, were at the non-striker's end when a ball was bowled, or were dismissed. Otherwise "did not bat" | C5 |
| R12 | Fielding | **Catches:** `caught` credits the listed fielder; `caught and bowled` credits the bowler. **Catches as a substitute** are kept separately and are not career catches. **Stumpings** credit the listed fielder. **Run-outs:** every listed fielder gets a "run-out involvement" (not a standard career stat; labelled as such) | C5, C6 |
| R13 | Match appearance | A player appears in a match if they are on the team sheet: XI, supersub, or a replacement who came in. Matches **abandoned without a ball bowled** are excluded from player match counts and team records. A no-result with some play counts as a match and a no-result | C10 |
| R14 | Tie decided by super over or bowl-out | Shown as **tied** in team records. The winner is stored (`decided_by`) and shown as "won the super over" | C7 |
| R15 | Fifties and hundreds | 50s = 50–99, 100s = 100+ (a hundred is not also a fifty). **Duck** = 0 and out (0* is not a duck). 4w = exactly 4 wickets in an innings, 5w = 5 or more | A1, A2 |
| R16 | High score | Highest runs in an innings. On equal runs, a not-out innings is shown (100*) | A1 |
| R17 | Ratios | Batting average = runs ÷ outs (no outs → "—"). Strike rate = runs × 100 ÷ balls faced. Bowling average = runs conceded ÷ wickets. Economy = runs conceded × 6 ÷ legal balls. Bowling SR = legal balls ÷ wickets | A1, A2 |
| R18 | Best bowling (BBI) | Most wickets in an innings, then fewest runs (5/41 beats 5/50 beats 4/10) | A2 |
| R19 | Team win % | won ÷ (matches − no results) × 100. Ties and draws stay in the denominator | A3 |
| R20 | Phases | Fixed over ranges from `phase_defs`. T20: 1–6, 7–15, 16–20. **ODI phases are labelled by overs ("Overs 1–10")**, not "powerplay", because ODI powerplay rules changed over the years. Reduced-overs matches keep the same fixed ranges | test |
| R21 | Formats | Every raw (match_type, team_type, balls_per_over) combination maps to one `format_key`. **A build fails on an unmapped combination**, so a new format is classified on purpose. Player tabs: Test, ODI, T20I, Leagues (T20_LEAGUE + HUNDRED, by competition), All | test |
| R22 | "All" scope | Sums across the official international formats + featured leagues only, never domestic first-class / List A (those join under "More formats" in v1.1) | — |
| R23 | Displayed ratios | Averages, strike rates, economy and win % are shown to 2 decimals **cut off, not rounded**, as published records show them (44.5989 → 44.59). The views and the API return unrounded numbers; pages and the golden comparison apply this rule (decided 2026-10-06 after Wikipedia agreed with us on every such case but the last digit) | golden |

## 2. Team-level facts
- **Innings total** = Σ `runs_total` + penalty runs, excluding super overs.
- **Wickets** in an innings = dismissals that count as out (R1), so a retired hurt batter is not a wicket.
- **Result:** win / tie / draw / no result, with the margin and `method` (D/L, VJD, Awarded, Lost fewer wickets).
  D/L results are counted as normal wins and are labelled on the scorecard.
- **Home / away / neutral:** a team is "home" when the venue's country (venue map, F3 decision 2) is the team's country.
  An international team's country is its own name. A league team has no country, so it is always shown as neutral or omitted.

## 3. Validation against published figures (the "golden" set)
Unit cases prove the rules. The golden set checks the real data **end to end** once the build step exists (P0).

1. **Choose about 50 players and 10 teams.** Cover men and women; Test, ODI, T20I and IPL; batters, bowlers and keepers;
   players whose careers are mostly after 2012 (good coverage) and a few from the early 2000s (coverage gaps); and India
   players (the featured team).
2. **Reference figures** are read **by hand** from public scorecards and records. Using reference sites for manual
   validation is allowed by our sources policy; no scraping. Each value is recorded in
   `docs/validation/golden-figures.csv` with the source and the date checked.
3. **Tolerance:** an exact match is expected for post-2012 careers. Any difference must be explained, e.g. a match
   missing from Cricsheet, or the Afghanistan exclusion. Unexplained differences block the release.
4. **Draft (2026-10-06):** `docs/validation/golden-selection.csv` + `golden-figures.csv`, produced by
   `cricstat-pipeline golden`. Teams are compared from 2016-01-01 (fully covered) to the latest data date, so the window
   moves forward with every build; player careers are compared whole, with a coverage hint where the data is thin.
   Because the figures keep growing, a checked row is snapshotted; once that player's or team's match count changes it
   becomes "stale" (re-check), while a figure that moves with an unchanged match count is a regression and fails.
5. **Run in CI:** the golden check runs after every full build. The result is published on the Methodology page as
   "N of M figures match exactly; differences explained."

## 4. What the agent sees
`semantic_catalog` gets one description per view and column, written from this document. For example,
`v_player_bowling.economy`: *"Runs conceded per 6 legal balls; byes, leg-byes and penalty runs are not charged to the
bowler; super overs excluded."* The agent's typed tools return the formula with every answer. That is how the
"How this was computed" panel on the Ask page gets its text.

## 5. Review decisions (2026-10-05)
1. **Run-out involvements: shown** on player pages as a separate, labelled column with the note *"Not an official
   statistic: counts each fielder listed in a run-out, so shared run-outs credit both."* It is excluded from the
   official Catches + Stumpings "Dismissals" total.
2. **"All" tab = international (official formats) + featured leagues.** Domestic first-class and List A are excluded (they
   come with "More formats" in v1.1).
3. **Golden set: includes India.** Well-known India men's and women's players, plus both India teams. Claude drafts the
   list when the build step exists, and the user adds or swaps names.
