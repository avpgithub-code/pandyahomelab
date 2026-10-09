# P1.6 staged page work (snapshot, 2026-10-09)

Copies of the staged assets that git otherwise ignores (`cricstat/tools/staging/web/` is gitignored,
and `cricstat/web/` is bind-mounted LIVE, so the branch can't hold them there). Not served by anything.

- `predictor.js` → `staging/web/assets/predictor.js` (new file)
- `cricstat.css` → `staging/web/assets/cricstat.css` (the P1.6 sections are appended at the end)
- `venues/*.jpg` → `staging/web/venues/` (8 venue photos; credits in
  `cricstat-models/tournaments/wc2027/venues.csv`; 7 from Commons via `tools/fetch_venue_photos.py`,
  Centurion from Flickr by hand: Dave Morton, Public Domain Mark 1.0, flickr.com/photos/forwarddefensive/49404965312)

To rebuild staging in a new session: `python3 cricstat/tools/gen_pages.py` (creates staging from
cricstat/web if missing, writes the HTML), then copy these three items into `staging/web/`.
**Delete this folder when P1.6 is deployed** (the files then live in `cricstat/web/`).
