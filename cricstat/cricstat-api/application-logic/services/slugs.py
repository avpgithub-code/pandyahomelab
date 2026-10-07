"""Public identifiers (F5 §2): surrogate keys never leave the API.

Team slug = name + men/women, e.g. india-men, mumbai-indians-men. When a club shares a name with
an international team of the same gender, the club gets "-club" (F5: "+ club for leagues").
"""
import re
from typing import Dict, List, Optional, Tuple

GENDER = {"male": "men", "female": "women"}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def player_slug(name: str, player_id: str) -> str:
    """Readable page slug; lookups use only the id (F5: /players/virat-kohli-ba607b88/)."""
    return "%s-%s" % (slugify(name), player_id)


class TeamSlugs:
    def __init__(self, teams: List[dict]):
        self.by_slug: Dict[str, dict] = {}
        self.by_key: Dict[int, str] = {}
        self.by_identity: Dict[Tuple[str, str, str], str] = {}
        intl = {(t["name"], t["gender"]) for t in teams if t["team_type"] == "international"}
        for t in sorted(teams, key=lambda t: (t["team_type"] != "international", -t["matches"])):
            base = "%s-%s" % (slugify(t["name"]), GENDER.get(t["gender"], t["gender"]))
            if t["team_type"] == "club" and (t["name"], t["gender"]) in intl:
                base += "-club"
            slug, n = base, 2
            while slug in self.by_slug:
                slug, n = "%s-%d" % (base, n), n + 1
            self.by_slug[slug] = dict(t, slug=slug)
            self.by_key[t["team_key"]] = slug
            self.by_identity[(t["name"], t["gender"], t["team_type"])] = slug

    def get(self, slug: str) -> Optional[dict]:
        return self.by_slug.get(slug)

    def slug(self, team_key: int) -> Optional[str]:
        return self.by_key.get(team_key)

    def find(self, name: str, gender: str, team_type: str) -> Optional[str]:
        return self.by_identity.get((name, gender, team_type))


def full_name(name: str, variants: List[str], preferred: Optional[str] = None) -> str:
    """The name people search for. Cricsheet names are scorecard style ('V Kohli'). Wikidata's
    English label (`preferred`, P0.5) wins when it is a full name with the same surname; else the
    shortest Register variant with the same surname whose other words are real names, not
    initials ('MS Dhoni' no, 'Mahendra Singh Dhoni' yes); else the scorecard name."""
    surname = name.split()[-1].lower() if name.split() else ""

    def is_full(v: str) -> bool:
        words = v.split()
        return (len(words) >= 2 and words[-1].lower() == surname
                and all(len(w) > 1 and not (w.isupper() and len(w) <= 3) and "." not in w
                        for w in words[:-1]))
    if preferred and is_full(preferred.strip()):
        return preferred.strip()
    full = [v for v in [name] + variants if is_full(v)]
    return min(full, key=lambda v: (len(v), v)) if full else name
