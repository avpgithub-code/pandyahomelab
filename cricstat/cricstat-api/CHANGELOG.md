# Changelog

## Unreleased

### Added (2026-10-07, P0.5)
- Player profile: `full_name` now prefers the Wikidata English label (same surname required),
  then the Register variant; `bio` carries date of birth, birthplace and country for sport from
  Wikidata (`source`); `photo` (self-hosted Commons thumbnail URL, size, licence, licence URL,
  author, file page) or null. Under-18s have no birth details or photo (applied by the build).
- Player pages: "Born …" line, the photo with its credit in the summary, the photo as og:image
  (twitter:card summary) and in the Person JSON-LD with birthDate, birthPlace and sameAs Wikidata.

### Added (2026-10-07, P0.6)
- Server-rendered page heads for search engines and link previews: `/pages/players/{slug}/` and
  `/pages/countries/{slug}/` return the static page shell (cricstat/web, mounted read-only) with
  the page's own title, description, canonical URL, robots rule, JSON-LD (ProfilePage/Person,
  SportsTeam) and a summary table inside the box the page's JavaScript fills. A wrong name in a
  player slug gets a 301 to the canonical one; an unknown id or team a real 404 (noindex).
- Pages below the index bar (10 official internationals or 20 featured-league matches; settings
  `CRICSTAT_INDEX_MIN_INTL` / `_LEAGUE`) get `noindex,follow`; club pages are noindex for now.
- `/pages/sitemap.xml`: every indexable player and international team, with last-match dates.
- `full_name` on the player profile: the Register's full-name variant ("Virat Kohli" for
  "V Kohli"), else the scorecard name.

### Added (2026-10-06)
- GET-only FastAPI service over the serving DB (F5): health, status, meta (scopes, competitions,
  metrics), search, players (profile, career, years, phases, splits, innings) and teams (list,
  identity, record, results, head to head, home/away, years, top players).
- One response envelope with provenance (data_as_of, build_id, filters, metric definitions,
  coverage, attribution); problem+json errors; ETag = build id with 304s; Cache-Control.
- Read-only, immutable SQLite connections reopened when the pipeline swaps in a new build;
  process-wide per-build caches, startup warm-up and a page-cache read-through of each new file.
- Per-query time limit (10 s) and limit ≤ 100 paging.
- Tests run the real pipeline on a synthetic dataset (no network), including a live swap.
