-- 0001: raw match store + ingest run log.
-- One row per Cricsheet match file, keyed by match_id (= ESPNcricinfo match ID).
-- json_zlib holds the file's exact bytes, zlib-compressed; sha256 is over those bytes.
-- Rows are never deleted: a match missing from a full download gets removed_at set.

CREATE TABLE matches_raw (
    match_id      TEXT PRIMARY KEY,
    sha256        TEXT NOT NULL,
    json_zlib     BLOB NOT NULL,
    json_bytes    INTEGER NOT NULL,   -- uncompressed size
    data_version  TEXT,               -- meta.data_version
    revision      INTEGER,            -- meta.revision
    match_type    TEXT,               -- info.match_type (Test, ODI, T20, ODM, MDM, IT20)
    gender        TEXT,               -- info.gender (male, female)
    team_type     TEXT,               -- info.team_type (international, club)
    start_date    TEXT,               -- first of info.dates, ISO YYYY-MM-DD
    teams         TEXT,               -- info.teams as a JSON array
    event_name    TEXT,               -- info.event.name (nullable)
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    updated_at    TEXT NOT NULL,      -- when the content last changed (or was first stored)
    removed_at    TEXT,               -- set when absent from a full download; cleared if it returns
    last_run_id   INTEGER
);

CREATE INDEX ix_matches_raw_start_date ON matches_raw (start_date);
CREATE INDEX ix_matches_raw_match_type ON matches_raw (match_type);
CREATE INDEX ix_matches_raw_gender     ON matches_raw (gender);

CREATE TABLE ingest_runs (
    run_id      INTEGER PRIMARY KEY,
    mode        TEXT NOT NULL,        -- full | recent
    source      TEXT NOT NULL,        -- URL or local zip path
    source_sha256 TEXT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,        -- running | success | dq_failed | error
    added       INTEGER NOT NULL DEFAULT 0,
    updated     INTEGER NOT NULL DEFAULT 0,
    unchanged   INTEGER NOT NULL DEFAULT 0,
    failed      INTEGER NOT NULL DEFAULT 0,
    removed     INTEGER NOT NULL DEFAULT 0,
    restored    INTEGER NOT NULL DEFAULT 0,
    skipped     INTEGER NOT NULL DEFAULT 0,   -- non-JSON zip members (README.txt)
    active_before INTEGER,
    active_after  INTEGER,
    notes       TEXT                          -- JSON: warnings, gate failures, sample bad files
);
