"""Wikipedia parsers: every layout and quirk found while drafting the supplement (2026-10-08)."""
from db_logic.sources import match_boxes, season_pages

TEAM_COLUMNS = """
==September==
===2023 Asia Cup===
{{main|2023 Asia Cup}}
{| class="wikitable"
! colspan="8"|Round-robin
|-
! No.
! Date
! Team 1
! Captain 1
! Team 2
! Captain 2
! Venue
! Result
|-
| [https://www.espncricinfo.com/ci/engine/match/1388397.html ODI 4631] || 3 September || {{cr|AFG}} || [[Hashmatullah Shahidi]] || {{cr|BAN}} || [[Shakib Al Hasan]] || [[Gaddafi Stadium]], [[Lahore]] || {{cr|BAN}} by 89 runs
|-
| [https://www.espncricinfo.com/ci/engine/match/1388400.html ODI 4633] || 5 September || {{cr|AFG}} || [[Hashmatullah Shahidi]] || {{cr|SL}} || [[Dasun Shanaka]] || [[Gaddafi Stadium]], [[Lahore]] || {{cr|SL}} by 2 runs ([[Duckworth–Lewis–Stern method|DLS]])
|}
"""

HOME_AWAY_CAPTAINS = """
===Afghanistan in Ireland===
{| class="wikitable"
! colspan="9"|ODI series
|-
! No.
! Date
! Home captain
! Away captain
! Venue
! Result
|-
| [http://www.espncricinfo.com/ci/engine/match/997958.html ODI 3760a] || 10 July || [[William Porterfield]] || [[Asghar Stanikzai]] || [[Stormont Cricket Ground]], [[Belfast]] || Match abandoned
|-
| [http://www.espncricinfo.com/ci/engine/match/997959.html ODI 3761] || 12 July || [[William Porterfield]] || [[Asghar Stanikzai]] || [[Stormont Cricket Ground]], [[Belfast]] || {{cr|AFG|2013}} by 39 runs
|}
"""

NAMED_CAPTAINS = """
===WCL Championship===
{| class="wikitable"
|-
! No.
! Date
! Afghanistan captain
! Scotland captain
! Venue
! Result
|-
| [http://www.espncricinfo.com/ci/engine/match/592270.html ODI 3341] || 6 March || [[Mohammad Nabi]] || [[Gordon Drummond]] || [[Sharjah Cricket Stadium]], [[Sharjah]] || {{cr|AFG|2013}} by 7 wickets
|}
"""

QUIRKS = """
===2018 Cricket World Cup Qualifier===
{| class="wikitable"
! colspan="9"|Group Stage
|-
! No.
! Date
! Group
! Team 1
! Captain 1
! Team 2
! Captain 2
! Venue
! Result
|-
| [http://www.espncricinfo.com/ci/engine/match/1133023.html ODI 4000] ||colspan=2|17 March || {{cr|HK}} || [[Babar Hayat]] || {{cr|PNG}} || [[Assad Vala]] || [[Old Hararians]], [[Harare]] || {{cr|PNG}} by 58 runs
|-
| [http://www.espncricinfo.com/ci/engine/series/643659.html ODI 3399] || 28 July || {{cr|ZIM}} || x || {{cr|IND}} || y || [[Harare Sports Club]], [[Harare]] || {{cr|IND}} by 7 wickets
|-
| [http://www.espncricinfo.com/ci/engine/match/1133024.html List A match] || 17 March || {{cr|NEP}} || x || {{cr|NED}} || y || [[Kwekwe Sports Club]], [[Kwekwe]] || {{cr|NED}} by 45 runs
|}
"""


def test_team_columns_dls_and_main_article():
    rows = season_pages.parse_page("International cricket in 2023", TEAM_COLUMNS)
    assert [(r["odi_no"], r["match_id"], r["date"], r["team1"], r["team2"]) for r in rows] == [
        ("4631", "1388397", "2023-09-03", "AFG", "BAN"), ("4633", "1388400", "2023-09-05", "AFG", "SL")]
    assert rows[0]["winner"] == "BAN" and rows[0]["margin"] == "89 runs"
    assert rows[1]["method"] == "D/L"
    assert rows[0]["article"] == "2023 Asia Cup"
    assert rows[0]["venue"] == "Gaddafi Stadium, Lahore"


def test_home_away_captains_take_teams_from_heading_and_abandoned_has_no_play():
    rows = season_pages.parse_page("International cricket in 2016", HOME_AWAY_CAPTAINS)
    assert [(r["team1"], r["team2"], r["teams_from"]) for r in rows] == [
        ("Afghanistan", "Ireland", "heading")] * 2
    assert rows[0]["odi_no"] == "3760a"
    assert (rows[0]["result"], rows[0]["has_play"]) == ("no_result", "0")
    assert (rows[1]["result"], rows[1]["winner"]) == ("win", "AFG")


def test_named_captain_columns_and_winter_season_year():
    rows = season_pages.parse_page("International cricket in 2012–13", NAMED_CAPTAINS)
    assert (rows[0]["team1"], rows[0]["team2"], rows[0]["teams_from"]) == \
        ("Afghanistan", "Scotland", "captain columns")
    assert rows[0]["date"] == "2013-03-06"          # Jan–Jun of a 2012–13 page → 2013


def test_colspan_keeps_columns_aligned_series_link_has_no_id_and_list_a_skipped():
    rows = season_pages.parse_page("International cricket in 2017–18", QUIRKS)
    assert [r["odi_no"] for r in rows] == ["4000", "3399"]     # "List A match" is not an ODI
    assert (rows[0]["team1"], rows[0]["team2"], rows[0]["winner"]) == ("HK", "PNG", "PNG")
    assert rows[1]["match_id"] is None                          # a series link, not a scorecard


def test_heading_variants():
    assert season_pages._teams_from_heading("New Zealand in Pakistan (April 2023)") == \
        ["New Zealand", "Pakistan"]
    assert season_pages._teams_from_heading("India in West Indies and the United States") == \
        ["India", "West Indies"]
    assert season_pages._teams_from_heading("Bangladesh Vs Netherlands in Scotland") == \
        ["Bangladesh", "Netherlands"]
    assert season_pages._teams_from_heading("2023 Asia Cup") == []


def test_results():
    assert season_pages.parse_result("Match & S/O tied<br/>({{cr|ENG}} won on boundary count)") \
        == {"result": "tie", "winner": "ENG", "method": None, "decided_by": "super_over",
            "has_play": "1", "margin": None}
    assert season_pages.parse_result("No result")["result"] == "no_result"
    assert season_pages.parse_result("No result")["has_play"] == "1"
    assert season_pages.parse_result("{{BAN}} by 10 wickets")["winner"] == "BAN"
    assert season_pages.parse_result("")["result"] is None          # cancelled / not yet played


BOXES = """
{{Limited overs international
  | date = 7 October 2010
  | team1 = {{cr-rt|KEN}}
  | team2 = {{cr|AFG|2013}}
  | result = Kenya won by 92 runs
  | report = [http://www.cricinfo.com/ci/engine/match/470624.html Scorecard]
  | venue = [[Gymkhana Club Ground]], [[Nairobi]]
}}
{{Single-innings cricket match
 | date = 1 April
 | team1 = {{cr-rt|SCO}}
 | team2 = {{flagicon|UAE}} [[United Arab Emirates national cricket team|UAE]]
 | result = {{cr|IRE}} won by 7 wickets
 | report = [http://content.cricinfo.com/iccwcq2009/engine/match/390204.html Scorecard]
}}
"""


def test_match_boxes_template_variants_and_yearless_dates():
    b = match_boxes.parse_boxes(BOXES)
    assert [(x["date"], x["team1"], x["team2"], x["match_id"]) for x in b] == [
        ("2010-10-07", "KEN", "AFG", "470624"),
        ("--04-01", "SCO", "United Arab Emirates", "390204")]
    assert match_boxes.same_date("--04-01", "2009-04-01")
    assert not match_boxes.same_date("--04-01", "2009-04-02")
    names = {"Kenya": "Kenya", "IRE": "Ireland"}
    assert match_boxes.box_outcome("Kenya won by 92 runs", names) == \
        {"result": "win", "winner": "Kenya"}
    assert match_boxes.box_outcome("{{cr|IRE}} won by 7 wickets", names)["winner"] == "Ireland"
    assert match_boxes.box_outcome("Match abandoned", names)["result"] == "no_result"
