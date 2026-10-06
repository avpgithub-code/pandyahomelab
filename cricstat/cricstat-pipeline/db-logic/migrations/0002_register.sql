-- 0002: Cricsheet Register (people.csv, names.csv), stored as received by `register`.
-- Replaced in full on every register run (one transaction); the run is logged in ingest_runs with
-- mode = 'register'. The serving-DB build turns these into players, player_external_ids and player_names.

CREATE TABLE register_people (
    identifier  TEXT PRIMARY KEY,     -- 8-hex Cricsheet id (= info.registry.people values)
    name        TEXT NOT NULL,
    unique_name TEXT NOT NULL,
    keys_json   TEXT NOT NULL         -- {"cricinfo": ["253802"], "cricbuzz": [...], ...}: the key_* columns
);

CREATE TABLE register_names (
    identifier TEXT NOT NULL,
    name       TEXT NOT NULL,
    PRIMARY KEY (identifier, name)
);
