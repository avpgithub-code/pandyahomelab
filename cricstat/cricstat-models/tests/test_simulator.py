"""P1.3: the tournament simulator, the rating-drift fit, no-result rates and stage scoring."""
import os
import random

import pytest

from application_logic.models import simulator as sim
from application_logic.models import uncertainty
from application_logic.services import conditions_service
from application_logic.services import tournament_backtest_service as tb
from db_logic.repository import tournament_store
from tests.conftest import ROOT

TOURN = os.path.join(ROOT, "tournaments")
P0 = sim.SimParams(home=0, k_update=0, sigma=0, nr={}, nr_default=0.0, tie=0.0)

FMT = {"teams": ["A", "B", "C"],
       "stages": [{"id": "league", "kind": "round_robin", "groups": {"L": ["A", "B", "C"]},
                   "advance": {"top": 2}},
                  {"id": "final", "kind": "knockout", "washout": "shared", "tie": "super_over"}],
       "final_standings": {"L": ["C", "B", "A"]}}


def _fx(no, stage, s1, s2, group="L", **kw):
    return dict({"match_no": str(no), "stage": stage, "group": group, "date": "2027-10-%02d" % no,
                 "slot1": s1, "slot2": s2, "venue_country": "X", "team1": "", "team2": "",
                 "result": "", "winner": "", "has_play": ""}, **kw)


FIX = [_fx(1, "league", "A", "B"), _fx(2, "league", "A", "C"), _fx(3, "league", "B", "C"),
       _fx(4, "final", "L1", "L2", group="")]


def test_strong_team_wins_and_stage_sums_hold():
    t = sim.Tournament(FMT, FIX)
    res = sim.simulate(t, {"A": 2200, "B": 1500, "C": 1500}, P0, 2000, 1)
    assert res.champion["A"] / res.n > 0.97
    assert tb.sums(res) == {"league": 3.0, "final": 2.0, "champion": 1.0}


def test_known_results_and_replay_use_official_standings():
    fx = [dict(FIX[0], team1="A", team2="B", result="no_result"),
          dict(FIX[1], team1="A", team2="C", result="no_result"),
          dict(FIX[2], team1="B", team2="C", result="no_result"), FIX[3]]
    t = sim.Tournament(FMT, fx)
    res = sim.simulate(t, {"A": 2200, "B": 1500, "C": 1500}, P0, 200, 3, replay=True)
    assert res.stage_counts["C"]["final"] == 200 and "final" not in res.stage_counts["A"]


def test_washouts_shared_final_and_higher_placed_semi():
    always_rain = P0._replace(nr={"X": 1.0})
    t = sim.Tournament(FMT, FIX)
    res = sim.simulate(t, {"A": 1500, "B": 1500, "C": 1500}, always_rain, 300, 5)
    assert sum(res.champion.values()) == pytest.approx(300.0)      # shared, half each
    assert all(v in (0.0, 150.0, 300.0) or v % 0.5 == 0 for v in res.champion.values())
    semi = {"id": "semi", "kind": "knockout", "washout": "higher_placed"}
    fmt = dict(FMT, stages=FMT["stages"][:1] + [semi])
    t2 = sim.Tournament(fmt, FIX[:3] + [_fx(4, "semi", "L1", "L2", group="")])
    r, _ = t2.play({"A": 1500, "B": 1500, "C": 1500}, always_rain, random.Random(1),
                   replay=True)
    assert r["semi"] == {"C", "B"}


def test_committed_past_world_cups_replay_exactly():
    for tid, champion in (("wc2019", "England"), ("wc2023", "Australia")):
        fmt = tournament_store.read_format(TOURN, tid)
        t = sim.Tournament(fmt, tournament_store.read_fixtures(TOURN, tid))
        res = sim.simulate(t, {}, P0._replace(nr_default=0.065, tie=0.01), 20, 1, replay=True)
        semis = sorted(k for k, v in res.stage_counts.items() if v.get("semi") == 20)
        assert semis == sorted(fmt["final_standings"]["L"][:4])
        assert res.champion == {champion: 20}


def test_2027_format_runs_with_qualifier_slots_and_both_group_assignments():
    fmt = tournament_store.read_format(TOURN, "wc2027")
    t = sim.Tournament(fmt, tournament_store.read_fixtures(TOURN, "wc2027"))
    field = ["Q-a", "Q-b", "Q-c", "Q-d", "Q-e"]
    ratings = dict({tm: 1500.0 for tm in fmt["teams"]}, **{q: 1300.0 for q in field})
    group_of_q1 = set()

    def draw(rng, noisy):
        order = sim.round_robin_order(field, noisy, P0, rng)
        return {"Q%d" % (i + 1): tm for i, tm in enumerate(order[:4])}

    rng = random.Random(9)
    for _ in range(40):
        slots = draw(rng, ratings)
        names = dict(slots)
        t._assign_qualifier_slots(names, rng)
        group_of_q1.add("A" if names["QA"] == slots["Q1"] else "B")
    assert group_of_q1 == {"A", "B"}                       # TBC rule: 50/50 until published
    res = sim.simulate(t, ratings, P0._replace(nr_default=0.06, tie=0.01, sigma=30, k_update=20),
                       300, 11, slot_draw=draw)
    s = tb.sums(res)
    for stage, n in (("super_series", 3), ("group", 12), ("super7", 7), ("semi", 4),
                     ("final", 2), ("qualified", 4), ("champion", 1)):
        assert s[stage] == pytest.approx(n), stage


def test_rating_drift_fit_recovers_a_random_walk():
    pts = {d: ((3.0 * d) ** 0.5, 100) for d in (30, 90, 365)}
    assert uncertainty.fit(pts) == pytest.approx(3.0)
    assert uncertainty.sigma(3.0, 300) == pytest.approx(30.0)


def test_no_result_rates_shrink_small_samples_and_ignore_later_matches():
    rows = [{"date": "2020-10-0%d" % (i % 9 + 1), "venue_country": "SA" if i < 10 else "IN",
             "result": "no_result" if i in (0, 1) or i >= 95 else "win"} for i in range(100)]
    r = conditions_service.rates(rows, "2021-01-01", ["SA"], [10], shrink=50)
    assert r["global"] == pytest.approx(7 / 100)
    assert r["by_country"]["SA"] == pytest.approx((2 + 50 * 0.07) / 60)
    later = conditions_service.rates(rows, "2020-01-01", ["SA"], [10])
    assert later["matches"] == 0


def test_stage_scoring():
    fmt = {"teams": ["A", "B"]}
    fixtures = [_fx(1, "semi", "L1", "L2", team1="A", team2="B"),
                _fx(2, "final", "W1", "W1", team1="A", team2="B", winner="A")]
    res = sim.Result({"A": {"semi": 10, "final": 8}, "B": {"semi": 10, "final": 2}},
                     {"A": 7, "B": 3}, 10)
    c = tb.test_c(fmt, fixtures, res)
    assert c["champion"] == "A" and c["p_champion"] == 0.7
    assert c["brier"]["champion"] == pytest.approx(((0.7 - 1) ** 2 + 0.3 ** 2) / 2)
