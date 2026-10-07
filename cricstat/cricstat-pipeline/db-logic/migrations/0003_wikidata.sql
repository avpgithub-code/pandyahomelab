-- 0003: Wikidata + Wikimedia Commons enrichment, written by `enrich` (P0.5).
-- People are matched ONLY by their ESPNcricinfo id (Wikidata property P2697, from the Register),
-- never by name. Runs are logged in ingest_runs with mode = 'enrich'. The serving-DB build turns
-- these into player_bio (full name, birth details, photo + credit).

CREATE TABLE wikidata_people (
    cricinfo_id       TEXT PRIMARY KEY,   -- Register key_cricinfo
    qid               TEXT,               -- NULL: looked up, not on Wikidata (re-checked later)
    label_en          TEXT,               -- English label, e.g. "Smriti Mandhana" (CC0)
    date_of_birth     TEXT,               -- YYYY-MM-DD, YYYY-MM or YYYY, by Wikidata's precision
    birthplace        TEXT,               -- English label of P19
    country_for_sport TEXT,               -- English label of P1532
    image_file        TEXT,               -- P18 file name on Commons (no "File:" prefix)
    fetched_at        TEXT NOT NULL
);

CREATE TABLE commons_images (
    image_file      TEXT PRIMARY KEY,     -- as in wikidata_people.image_file
    status          TEXT NOT NULL,        -- ok | rejected (licence not allowed) | error
    licence         TEXT,                 -- LicenseShortName, e.g. "CC BY-SA 4.0", "Public domain"
    licence_url     TEXT,
    author          TEXT,                 -- plain text (Commons' Artist field, HTML removed)
    description_url TEXT,                 -- the file's Commons page (credit link)
    thumb_path      TEXT,                 -- under CRICSTAT_PHOTO_DIR, e.g. 3f2a….jpg (about 330 px wide)
    width           INTEGER,
    height          INTEGER,
    note            TEXT,                 -- why rejected / the error
    fetched_at      TEXT NOT NULL
);
