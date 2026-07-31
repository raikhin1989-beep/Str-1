"""Работа с данными: дегустации, справочник виски, состав дегустации."""

import random
import secrets
import sqlite3

from app.db import connect

# Машина состояний дегустации. Порядок жёсткий: раунд по вкусу не открыть,
# пока не закрыт раунд по запаху, итоги не посчитать при открытом раунде.
STATUSES = ["draft", "registration", "round_nose", "round_palate", "scoring", "closed"]

STATUS_TITLES = {
    "draft": "черновик",
    "registration": "регистрация",
    "round_nose": "раунд по запаху",
    "round_palate": "раунд по вкусу",
    "scoring": "подсчёт итогов",
    "closed": "завершена",
}

# Из какого статуса куда можно перейти. Назад — только на шаг, и только до
# начала раундов: после того как люди начали отвечать, откат ломает данные.
ALLOWED_TRANSITIONS = {
    "draft": ["registration"],
    "registration": ["draft", "round_nose"],
    "round_nose": ["round_palate"],
    "round_palate": ["scoring"],
    "scoring": ["closed"],
    "closed": [],
}

# Состав дегустации можно менять и перемешивать только до начала раундов.
EDITABLE_STATUSES = {"draft", "registration"}

WHISKY_CLASSES = [
    "односолодовый скотч",
    "купажированный скотч",
    # Односолодовый не из Шотландии — отдельный класс, а не «прочее»: иначе
    # русский односолодовый и теннесси попали бы в одну корзину и частичный
    # балл давался бы за то, что общего между ними нет (docs/SCORING.md).
    "односолодовый (не Шотландия)",
    "бурбон",
    "теннесси",
    "ржаной",
    "прочее",
]

CATEGORY_LEVELS = {"class": "по классу", "region": "по региону"}


# ── дегустации ─────────────────────────────────────────────────────────────


def list_tastings() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT t.*, (SELECT COUNT(*) FROM tasting_whisky tw"
            "             WHERE tw.tasting_id = t.id) AS sample_count,"
            "       (SELECT COUNT(*) FROM participant p"
            "             WHERE p.tasting_id = t.id) AS participant_count"
            " FROM tasting t ORDER BY t.id DESC"
        ).fetchall()


def get_tasting(tasting_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM tasting WHERE id = ?", (tasting_id,)).fetchone()


def create_tasting(title: str, held_on: str | None, category_level: str) -> int:
    if category_level not in CATEGORY_LEVELS:
        raise ValueError("неизвестная гранулярность категорий")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasting (title, held_on, category_level, public_code)"
            " VALUES (?, ?, ?, ?)",
            (
                title.strip(),
                (held_on or "").strip() or None,
                category_level,
                secrets.token_urlsafe(9),
            ),
        )
        return int(cur.lastrowid)


def get_tasting_by_code(code: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM tasting WHERE public_code = ?", (code,)
        ).fetchone()


def update_tasting(tasting_id: int, title: str, held_on: str | None, category_level: str) -> None:
    if category_level not in CATEGORY_LEVELS:
        raise ValueError("неизвестная гранулярность категорий")
    with connect() as conn:
        conn.execute(
            "UPDATE tasting SET title = ?, held_on = ?, category_level = ? WHERE id = ?",
            (title.strip(), (held_on or "").strip() or None, category_level, tasting_id),
        )


def set_status(tasting_id: int, new_status: str) -> None:
    """Сменить статус, если такой переход разрешён."""
    with connect() as conn:
        row = conn.execute("SELECT status FROM tasting WHERE id = ?", (tasting_id,)).fetchone()
        if row is None:
            raise ValueError("дегустация не найдена")
        current = row["status"]
        if new_status not in ALLOWED_TRANSITIONS.get(current, []):
            raise ValueError(
                f"переход «{STATUS_TITLES.get(current, current)}» → "
                f"«{STATUS_TITLES.get(new_status, new_status)}» не разрешён"
            )
        conn.execute("UPDATE tasting SET status = ? WHERE id = ?", (new_status, tasting_id))


# ── справочник виски ───────────────────────────────────────────────────────

WHISKY_FIELDS = [
    "name", "distillery", "wclass", "region", "abv", "age_years", "cask",
    "grain", "filtration", "price_rub", "colour", "nose", "palate", "finish", "notes",
]


def list_whiskies() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM whisky ORDER BY name COLLATE NOCASE").fetchall()


def get_whisky(whisky_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM whisky WHERE id = ?", (whisky_id,)).fetchone()


def search_whiskies(query: str) -> list[sqlite3.Row]:
    """Поиск по названию, винокурне и региону.

    Фильтруем в Python, а не в SQL: LIKE в SQLite регистронезависим только для
    латиницы, и «аберлауэр» не нашёл бы «Аберлауэр». Справочник — десятки
    записей, разница в скорости незаметна.
    """
    needle = query.strip().casefold()
    if not needle:
        return list_whiskies()
    return [
        row
        for row in list_whiskies()
        if any(
            needle in (row[field] or "").casefold()
            for field in ("name", "distillery", "region")
        )
    ]


def save_whisky(data: dict, whisky_id: int | None = None, source: str = "manual") -> int:
    """Создать или обновить запись справочника.

    source='ai' помечает карточку, полученную от модели: на публичной странице
    у такой стоит пометка «данные ориентировочные». Правка через админку
    источник не меняет — пометка снимается вручную, когда данные сверены.
    """
    values = {k: _clean(data.get(k)) for k in WHISKY_FIELDS}
    if not values["name"]:
        raise ValueError("у виски должно быть название")
    for numeric, caster in (("abv", float), ("age_years", int), ("price_rub", int)):
        if values[numeric] is not None:
            try:
                values[numeric] = caster(str(values[numeric]).replace(",", "."))
            except ValueError:
                raise ValueError(f"поле «{numeric}» должно быть числом") from None

    with connect() as conn:
        if whisky_id is None:
            columns = ", ".join(WHISKY_FIELDS)
            marks = ", ".join("?" for _ in WHISKY_FIELDS)
            cur = conn.execute(
                f"INSERT INTO whisky ({columns}, source) VALUES ({marks}, ?)",
                [values[k] for k in WHISKY_FIELDS] + [source],
            )
            return int(cur.lastrowid)
        assignments = ", ".join(f"{k} = ?" for k in WHISKY_FIELDS)
        conn.execute(
            f"UPDATE whisky SET {assignments} WHERE id = ?",
            [values[k] for k in WHISKY_FIELDS] + [whisky_id],
        )
        return whisky_id


def _clean(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ── состав дегустации ──────────────────────────────────────────────────────


def tasting_whiskies(tasting_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT tw.sample_no, w.* FROM tasting_whisky tw"
            " JOIN whisky w ON w.id = tw.whisky_id"
            " WHERE tw.tasting_id = ? ORDER BY tw.sample_no",
            (tasting_id,),
        ).fetchall()


def add_whisky_to_tasting(tasting_id: int, whisky_id: int) -> None:
    _require_editable(tasting_id)
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM tasting_whisky WHERE tasting_id = ? AND whisky_id = ?",
            (tasting_id, whisky_id),
        ).fetchone()
        if exists:
            raise ValueError("этот виски уже в составе дегустации")
        next_no = conn.execute(
            "SELECT COALESCE(MAX(sample_no), 0) + 1 AS n FROM tasting_whisky WHERE tasting_id = ?",
            (tasting_id,),
        ).fetchone()["n"]
        conn.execute(
            "INSERT INTO tasting_whisky (tasting_id, whisky_id, sample_no) VALUES (?, ?, ?)",
            (tasting_id, whisky_id, next_no),
        )


def remove_whisky_from_tasting(tasting_id: int, whisky_id: int) -> None:
    _require_editable(tasting_id)
    with connect() as conn:
        conn.execute(
            "DELETE FROM tasting_whisky WHERE tasting_id = ? AND whisky_id = ?",
            (tasting_id, whisky_id),
        )
        _renumber(conn, tasting_id)


def shuffle_samples(tasting_id: int) -> None:
    """Перемешать номера образцов.

    Номера — единственное, что скрывает от участников, что где налито,
    поэтому назначаются случайно и только до начала раундов.
    """
    _require_editable(tasting_id)
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM tasting_whisky WHERE tasting_id = ?", (tasting_id,)
        ).fetchall()
        numbers = list(range(1, len(rows) + 1))
        random.shuffle(numbers)
        # Двумя проходами: UNIQUE(tasting_id, sample_no) не даст переставить
        # номера напрямую, промежуточные значения уводим в отрицательные.
        for row, number in zip(rows, numbers):
            conn.execute("UPDATE tasting_whisky SET sample_no = ? WHERE id = ?", (-number, row["id"]))
        conn.execute(
            "UPDATE tasting_whisky SET sample_no = -sample_no WHERE tasting_id = ?", (tasting_id,)
        )


def _renumber(conn: sqlite3.Connection, tasting_id: int) -> None:
    """Сжать номера до 1..N после удаления образца."""
    rows = conn.execute(
        "SELECT id FROM tasting_whisky WHERE tasting_id = ? ORDER BY sample_no", (tasting_id,)
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        conn.execute("UPDATE tasting_whisky SET sample_no = ? WHERE id = ?", (-index, row["id"]))
    conn.execute(
        "UPDATE tasting_whisky SET sample_no = -sample_no WHERE tasting_id = ?", (tasting_id,)
    )


# ── участники ──────────────────────────────────────────────────────────────


def list_participants(tasting_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM participant WHERE tasting_id = ? ORDER BY id",
            (tasting_id,),
        ).fetchall()


def get_participant_by_token(token: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM participant WHERE join_token = ?", (token,)
        ).fetchone()


def register_participant(tasting_id: int, name: str) -> str:
    """Записать гостя и вернуть его личный токен.

    Токен — и адрес личной страницы, и полезная нагрузка deep link'а телеграма,
    по которой бот понимает, кого привязывает.
    """
    clean = " ".join(name.split())
    if not clean:
        raise ValueError("нужно имя")
    if len(clean) > 60:
        raise ValueError("имя слишком длинное")

    tasting = get_tasting(tasting_id)
    if tasting is None:
        raise ValueError("дегустация не найдена")
    if tasting["status"] != "registration":
        raise ValueError("регистрация на эту дегустацию сейчас закрыта")

    token = secrets.token_urlsafe(16)
    with connect() as conn:
        conn.execute(
            "INSERT INTO participant (tasting_id, name, join_token) VALUES (?, ?, ?)",
            (tasting_id, clean, token),
        )
    return token


def link_telegram(token: str, chat_id: int, username: str | None) -> sqlite3.Row | None:
    """Привязать телеграм-аккаунт к участнику по токену из deep link'а."""
    with connect() as conn:
        participant = conn.execute(
            "SELECT * FROM participant WHERE join_token = ?", (token,)
        ).fetchone()
        if participant is None:
            return None
        conn.execute(
            "UPDATE participant SET tg_chat_id = ?, tg_username = ? WHERE id = ?",
            (chat_id, username, participant["id"]),
        )
        return conn.execute(
            "SELECT * FROM participant WHERE id = ?", (participant["id"],)
        ).fetchone()


def _require_editable(tasting_id: int) -> None:
    tasting = get_tasting(tasting_id)
    if tasting is None:
        raise ValueError("дегустация не найдена")
    if tasting["status"] not in EDITABLE_STATUSES:
        raise ValueError(
            "состав нельзя менять после начала раундов "
            f"(статус: {STATUS_TITLES.get(tasting['status'], tasting['status'])})"
        )
