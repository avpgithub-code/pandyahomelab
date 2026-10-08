"""Monte Carlo tournament simulator (P1 plan §2.4). One engine for every format in tournaments/.

Each simulated tournament:
  1. every team's rating gets one draw of N(0, sigma) (uncertainty about its strength by then);
  2. stages run in the order format.json lists them. Round robins: win 2, tie/no result 1 point;
     standings by points, then wins, then a random draw (NRR isn't simulated). In a replay the
     official final standings settle ties instead. Knockouts: a washout (both the day and the
     reserve day, p_nr squared) sends the higher-placed side (slot1) through, a washed-out final is
     shared; a tie goes to a super over (50/50);
  3. a match with a known result (fixtures.csv team1/team2/result) uses it instead of a draw;
  4. ratings optionally move after each simulated match (k_update), as Elo would during the event.
Placeholders: <group><place> (A1, L4), the stage's advance.as names (SSW, S7-1), 4TH = best 4th
place across groups, W<match no.> = a knockout winner, Q1..Q4 = Qualifier places, QA/QB = the two
qualifier slots in the groups (Qualifier winner and Super Series winner, assignment per format).
"""
import random
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

from application_logic.models.elo import probability


class SimParams(NamedTuple):
    home: float                    # Elo points for a team playing in its own country
    k_update: float                # 0 = ratings frozen during a simulated tournament
    sigma: float                   # SD of the per-team rating draw (Elo points)
    nr: Dict[str, float]           # venue country -> P(no result)
    nr_default: float
    tie: float                     # P(tie | a result)


SlotDraw = Callable[[random.Random, Dict[str, float]], Dict[str, str]]


class Result(NamedTuple):
    stage_counts: Dict[str, Dict[str, float]]   # team -> stage id -> times reached
    champion: Dict[str, float]
    n: int


def _match(a: str, b: str, country: Optional[str], r: Dict[str, float], p: SimParams,
           rng: random.Random, knockout: bool) -> Tuple[str, Optional[str]]:
    """('win', winner) | ('tie', None) | ('no_result', None) for a simulated match."""
    p_nr = p.nr.get(country or "", p.nr_default)
    if knockout:
        p_nr = p_nr * p_nr                       # the reserve day washed out too
    if rng.random() < p_nr:
        return "no_result", None
    h = 1 if country == a else -1 if country == b else 0
    e = probability(r.get(a, 1500.0), r.get(b, 1500.0), p.home, h)
    if rng.random() < p.tie:
        return "tie", None
    winner = a if rng.random() < e else b
    if p.k_update:
        s = 1.0 if winner == a else 0.0
        r[a] = r.get(a, 1500.0) + p.k_update * (s - e)
        r[b] = r.get(b, 1500.0) - p.k_update * (s - e)
    return "win", winner


class Tournament:
    def __init__(self, fmt: Dict[str, object], fixtures: List[Dict[str, str]]):
        self.fmt = fmt
        self.stages = fmt["stages"]
        self.by_stage: Dict[str, List[Dict[str, str]]] = {}
        for f in sorted(fixtures, key=lambda f: (f["date"], int(f["match_no"]))):
            self.by_stage.setdefault(f["stage"], []).append(f)
        self.official = fmt.get("final_standings") or {}

    # -- one simulated tournament --------------------------------------------------------------
    def play(self, ratings: Dict[str, float], p: SimParams, rng: random.Random,
             slots: Optional[Dict[str, str]] = None, replay: bool = False,
             use_known: bool = True) -> Tuple[Dict[str, set], Dict[str, float]]:
        """Returns (stage id -> teams that played in it, champion -> share)."""
        r = dict(ratings)
        if p.sigma:
            for t in list(r):
                r[t] += rng.gauss(0.0, p.sigma)
        names: Dict[str, str] = dict(slots or {})
        reached: Dict[str, set] = {}
        champion: Dict[str, float] = {}
        for st in self.stages:
            fixtures = self.by_stage.get(st["id"], [])
            if st["id"] == "group" and "QA" in str(st.get("groups")) and "QA" not in names:
                self._assign_qualifier_slots(names, rng)
            if st["kind"] == "round_robin":
                self._round_robin(st, fixtures, names, r, p, rng, reached, replay, use_known)
            else:
                self._knockout(st, fixtures, names, r, p, rng, reached, champion, use_known)
        return reached, champion

    def _resolve(self, slot: str, names: Dict[str, str]) -> str:
        return names.get(slot, slot)

    def _assign_qualifier_slots(self, names: Dict[str, str], rng: random.Random) -> None:
        q = self.fmt.get("qualifier", {})
        fixed = q.get("fixed_slots")              # e.g. {"QA": "Q1", "QB": "SSW"} once published
        order = (fixed["QA"], fixed["QB"]) if fixed else \
            (("Q1", "SSW") if rng.random() < 0.5 else ("SSW", "Q1"))
        names["QA"], names["QB"] = names.get(order[0], order[0]), names.get(order[1], order[1])

    def _known(self, f, a, b, use_known):
        if use_known and f.get("result") and {f.get("team1"), f.get("team2")} == {a, b}:
            return f["result"], (f.get("winner") or None)
        return None

    def _round_robin(self, st, fixtures, names, r, p, rng, reached, replay, use_known):
        table: Dict[str, Dict[str, List[float]]] = {}
        for g, members in st["groups"].items():
            table[g] = {self._resolve(m, names): [0.0, 0.0] for m in members}
        for f in fixtures:
            a, b = self._resolve(f["slot1"], names), self._resolve(f["slot2"], names)
            g = f["group"]
            res = self._known(f, a, b, use_known) or _match(a, b, f["venue_country"], r, p, rng,
                                                            False)
            kind, winner = res
            if kind == "win":
                table[g][winner][0] += 2
                table[g][winner][1] += 1
            else:                                   # tie or no result: a point each
                table[g][a][0] += 1
                table[g][b][0] += 1
        adv = st.get("advance", {})
        fourths = []
        for g, rows in table.items():
            for t in rows:
                reached.setdefault(st["id"], set()).add(t)
            if replay and g in self.official:
                pos = {t: i for i, t in enumerate(self.official[g])}
                order = sorted(rows, key=lambda t: pos.get(t, 99))
            else:
                order = sorted(rows, key=lambda t: (-rows[t][0], -rows[t][1], rng.random()))
            top = adv.get("top", 0)
            as_names = adv.get("as")
            for i, t in enumerate(order[:top]):
                names[as_names[i] if as_names else "%s%d" % (g, i + 1)] = t
            best = adv.get("best_of_rest")
            if best and len(order) >= best["place"]:
                t = order[best["place"] - 1]
                fourths.append((rows[t][0], rows[t][1], rng.random(), t))
        if fourths:
            fourths.sort(reverse=True)
            names[adv["best_of_rest"]["as"]] = fourths[0][3]

    def _knockout(self, st, fixtures, names, r, p, rng, reached, champion, use_known):
        for f in fixtures:
            a, b = self._resolve(f["slot1"], names), self._resolve(f["slot2"], names)
            reached.setdefault(st["id"], set()).update((a, b))
            res = self._known(f, a, b, use_known) or _match(a, b, f["venue_country"], r, p, rng,
                                                            True)
            kind, winner = res
            if kind == "tie" and not winner:
                winner = a if rng.random() < 0.5 else b          # super over
            if kind == "no_result":
                if st.get("washout") == "shared":
                    champion[a] = champion.get(a, 0) + 0.5
                    champion[b] = champion.get(b, 0) + 0.5
                    continue
                winner = a                                        # higher placed goes through
            names["W%s" % f["match_no"]] = winner
            if st["id"] == "final":
                champion[winner] = champion.get(winner, 0) + 1.0


def simulate(t: Tournament, ratings: Dict[str, float], p: SimParams, n: int, seed: int,
             slot_draw: Optional[SlotDraw] = None,
             replay: bool = False, use_known: bool = True) -> Result:
    """Run n tournaments. slot_draw(rng, noisy ratings) supplies Q1..Q4 when the field is open."""
    rng = random.Random(seed)
    counts: Dict[str, Dict[str, float]] = {}
    champ: Dict[str, float] = {}
    frozen = p._replace(sigma=0.0)
    for _ in range(n):
        # One draw of each team's uncertainty per simulated tournament, shared by the Qualifier and
        # the World Cup (a team that's stronger than its rating is stronger in both).
        noisy = {tm: v + rng.gauss(0.0, p.sigma) for tm, v in ratings.items()} if p.sigma \
            else dict(ratings)
        slots = slot_draw(rng, noisy) if slot_draw else None
        reached, won = t.play(noisy, frozen, rng, slots, replay, use_known)
        if slots:
            reached["qualified"] = set(slots.values())      # took one of the Qualifier places
        for stage, teams in reached.items():
            for tm in teams:
                c = counts.setdefault(tm, {})
                c[stage] = c.get(stage, 0) + 1
        for tm, share in won.items():
            champ[tm] = champ.get(tm, 0) + share
    return Result(counts, champ, n)


def round_robin_order(teams: List[str], ratings: Dict[str, float], p: SimParams,
                      rng: random.Random, country: Optional[str] = None) -> List[str]:
    """One single round robin (used for the Qualifier while its format is unpublished)."""
    pts = {t: [0.0, 0.0, rng.random()] for t in teams}
    for i, a in enumerate(teams):
        for b in teams[i + 1:]:
            kind, w = _match(a, b, country, ratings, p._replace(k_update=0), rng, False)
            if kind == "win":
                pts[w][0] += 2
                pts[w][1] += 1
            else:
                pts[a][0] += 1
                pts[b][0] += 1
    return sorted(teams, key=lambda t: (-pts[t][0], -pts[t][1], pts[t][2]))
