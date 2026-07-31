-- Начальная схема. Описание полей и правил — в docs/DATA-MODEL.md.

-- Дегустация. status — машина состояний, переходы проверяются в коде:
-- draft → registration → round_nose → round_palate → scoring → closed.
CREATE TABLE tasting (
    id             INTEGER PRIMARY KEY,
    title          TEXT NOT NULL,
    held_on        TEXT,
    status         TEXT NOT NULL DEFAULT 'draft',
    category_level TEXT NOT NULL DEFAULT 'class',
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Справочник виски. source: manual — введено админом, ai — получено моделью.
CREATE TABLE whisky (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    distillery  TEXT,
    wclass      TEXT,
    region      TEXT,
    abv         REAL,
    age_years   INTEGER,
    cask        TEXT,
    grain       TEXT,
    filtration  TEXT,
    price_rub   INTEGER,
    colour      TEXT,
    nose        TEXT,
    palate      TEXT,
    finish      TEXT,
    notes       TEXT,
    source      TEXT NOT NULL DEFAULT 'manual',
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Что наливается на конкретной дегустации и под каким номером.
CREATE TABLE tasting_whisky (
    id         INTEGER PRIMARY KEY,
    tasting_id INTEGER NOT NULL REFERENCES tasting(id) ON DELETE CASCADE,
    whisky_id  INTEGER NOT NULL REFERENCES whisky(id)  ON DELETE RESTRICT,
    sample_no  INTEGER NOT NULL,
    UNIQUE (tasting_id, sample_no),
    UNIQUE (tasting_id, whisky_id)
);

CREATE TABLE participant (
    id          INTEGER PRIMARY KEY,
    tasting_id  INTEGER NOT NULL REFERENCES tasting(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    join_token  TEXT NOT NULL UNIQUE,
    tg_chat_id  INTEGER,
    tg_username TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Ответ участника: какой виски он считает этим образцом.
-- Два UNIQUE: один ответ на образец и одно название нельзя поставить дважды.
CREATE TABLE answer (
    id             INTEGER PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
    round          TEXT NOT NULL,
    sample_no      INTEGER NOT NULL,
    whisky_id      INTEGER NOT NULL REFERENCES whisky(id) ON DELETE RESTRICT,
    submitted_at   TEXT,
    UNIQUE (participant_id, round, sample_no),
    UNIQUE (participant_id, round, whisky_id)
);

-- Личная оценка образца. Оценивается номер, а не название: в этот момент
-- участник ещё не знает, что налито.
CREATE TABLE rating (
    id             INTEGER PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
    sample_no      INTEGER NOT NULL,
    score          INTEGER,
    tags           TEXT,
    UNIQUE (participant_id, sample_no)
);

-- Кэш итогов: пересчитывается из answer целиком, источником истины не является.
CREATE TABLE result (
    participant_id  INTEGER PRIMARY KEY REFERENCES participant(id) ON DELETE CASCADE,
    points_nose     INTEGER NOT NULL DEFAULT 0,
    points_palate   INTEGER NOT NULL DEFAULT 0,
    points_partial  INTEGER NOT NULL DEFAULT 0,
    points_bonus    INTEGER NOT NULL DEFAULT 0,
    total           INTEGER NOT NULL DEFAULT 0,
    place           INTEGER,
    computed_at     TEXT
);

-- Кэш ответов модели: повторный запрос того же виски не идёт в API.
CREATE TABLE ai_cache (
    key        TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE admin_session (
    token      TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    ip         TEXT
);

-- Журнал действий: чтобы после вечера можно было разобраться, что произошло.
CREATE TABLE audit_log (
    id      INTEGER PRIMARY KEY,
    at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip      TEXT,
    action  TEXT NOT NULL,
    details TEXT
);

CREATE INDEX idx_tasting_whisky_tasting ON tasting_whisky(tasting_id);
CREATE INDEX idx_participant_tasting    ON participant(tasting_id);
CREATE INDEX idx_answer_participant     ON answer(participant_id);
