"""Работа с данными: дегустации, справочник виски, состав дегустации."""

import json
import random
import re
import secrets
import sqlite3

from app import scoring
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

# Класс важен не косметически: по нему начисляются частичные баллы. Список —
# компромисс между точностью и тем, что человек за столом различает вслепую.
# Ирландский и японский вынесены по происхождению, а не по типу: спутать
# Yamazaki с Hakushu — понятная ошибка, и балл за неё уместен, а вот
# «односолодовый» их с Тайванем и Индией не роднит.
WHISKY_CLASSES = [
    "односолодовый скотч",
    "купажированный скотч",
    # Односолодовый не из Шотландии — отдельный класс, а не «прочее»: иначе
    # русский односолодовый и теннесси попали бы в одну корзину и частичный
    # балл давался бы за то, что общего между ними нет (docs/SCORING.md).
    "односолодовый (не Шотландия)",
    "ирландский",
    "японский",
    "бурбон",
    "теннесси",
    "ржаной",
    "прочее",
]

CATEGORY_LEVELS = {"class": "по классу", "region": "по региону"}


def category_title(tasting) -> str:
    """Как в этой дегустации называется то, за что даётся частичный балл.

    Одно место на весь проект намеренно. Подпись стоит в семи местах —
    итоги, экран проектора, админка, страница гостя, сообщение в телеграм, —
    и когда она жила отдельной строкой в каждом, дегустация по регионам
    везде рассказывала гостям про класс. Так и случилось на живом вечере.
    """
    return "регион" if tasting["category_level"] == "region" else "класс"


# Из чего участник выбирает ответ. Справочник целиком — сложнее и честнее:
# частичный балл за класс начинает что-то значить, потому что можно назвать
# виски, которого на столе нет. Только налитое — режим полегче.
ANSWER_SCOPES = {"catalogue": "из всего справочника", "tasting": "только из налитого"}


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


def create_tasting(
    title: str,
    held_on: str | None,
    category_level: str,
    answer_scope: str = "catalogue",
) -> int:
    if category_level not in CATEGORY_LEVELS:
        raise ValueError("неизвестная гранулярность категорий")
    if answer_scope not in ANSWER_SCOPES:
        raise ValueError("неизвестный набор вариантов ответа")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasting (title, held_on, category_level, answer_scope, public_code)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                title.strip(),
                (held_on or "").strip() or None,
                category_level,
                answer_scope,
                secrets.token_urlsafe(9),
            ),
        )
        return int(cur.lastrowid)


def get_tasting_by_code(code: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM tasting WHERE public_code = ?", (code,)
        ).fetchone()


def update_tasting(
    tasting_id: int,
    title: str,
    held_on: str | None,
    category_level: str,
    answer_scope: str | None = None,
) -> None:
    if category_level not in CATEGORY_LEVELS:
        raise ValueError("неизвестная гранулярность категорий")
    if answer_scope is not None and answer_scope not in ANSWER_SCOPES:
        raise ValueError("неизвестный набор вариантов ответа")
    with connect() as conn:
        if answer_scope is not None:
            # Менять набор вариантов после начала раундов нельзя: у половины
            # стола ответы уже лежат из другого списка.
            current = conn.execute(
                "SELECT status FROM tasting WHERE id = ?", (tasting_id,)
            ).fetchone()
            if current and current["status"] not in EDITABLE_STATUSES:
                answer_scope = None
        if answer_scope is None:
            conn.execute(
                "UPDATE tasting SET title = ?, held_on = ?, category_level = ? WHERE id = ?",
                (title.strip(), (held_on or "").strip() or None, category_level, tasting_id),
            )
        else:
            conn.execute(
                "UPDATE tasting SET title = ?, held_on = ?, category_level = ?,"
                " answer_scope = ? WHERE id = ?",
                (
                    title.strip(),
                    (held_on or "").strip() or None,
                    category_level,
                    answer_scope,
                    tasting_id,
                ),
            )


def set_status(tasting_id: int, new_status: str) -> None:
    """Сменить статус, если такой переход разрешён.

    Закрытие раунда замораживает и черновики: человек, который расставил
    образцы, но не нажал «Отправить», не должен остаться вовсе без ответа.
    Забыть кнопку на вечеринке — обычное дело, а восстановить ответ потом
    уже нельзя.
    """
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
        closing = ROUND_BY_STATUS.get(current)
        if closing:
            for table in ("answer", "answer_category"):
                conn.execute(
                    f"UPDATE {table} SET submitted_at = CURRENT_TIMESTAMP"
                    " WHERE round = ? AND submitted_at IS NULL AND participant_id IN"
                    "       (SELECT id FROM participant WHERE tasting_id = ?)",
                    (closing, tasting_id),
                )
        conn.execute("UPDATE tasting SET status = ? WHERE id = ?", (new_status, tasting_id))


# ── справочник виски ───────────────────────────────────────────────────────

WHISKY_FIELDS = [
    "name", "distillery", "wclass", "region", "abv", "age_years", "cask",
    "grain", "filtration", "price_rub", "colour", "nose", "palate", "finish", "notes",
]


def by_name(rows) -> list[sqlite3.Row]:
    """Отсортировать по названию по-человечески.

    Не `ORDER BY ... COLLATE NOCASE`: эта коллация в SQLite складывает регистр
    только для латиницы. «Кемля» у неё оказывается раньше «далмор квотер», и
    для глаза список выглядит как попало — а гость видит его в раунде и ищет
    в нём название. Записей десятки, сортировка в Python ничего не стоит.
    """
    return sorted(rows, key=lambda row: (row["name"] or "").casefold())


def list_whiskies() -> list[sqlite3.Row]:
    with connect() as conn:
        return by_name(conn.execute("SELECT * FROM whisky").fetchall())


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


# Слова, которые есть почти на каждой этикетке и ничего не говорят о том,
# что именно в бутылке. Убираем их с обеих сторон сравнения — и из названия
# в справочнике, и из прочитанного текста.
#
# Список нарочно короткий. Каждое лишнее слово здесь — это потерянный признак:
# «Highland» выкинуть нельзя, иначе Highland Park сравняется с любым хайлендом,
# а «Reserve» и «Cask» стоят в самих названиях розливов.
LABEL_NOISE = {
    "whisky", "whiskey", "scotch", "single", "malt", "blended", "blend",
    "distillery", "distilled", "distillers", "aged", "age", "years", "year",
    "old", "vol", "alc", "abv", "cl", "ml", "litre", "liter", "the", "of",
    "and", "est", "product", "виски", "шотландский", "солодовый", "выдержка",
    "лет", "года", "год",
}


def _label_tokens(text: str) -> set[str]:
    """Слова, по которым имеет смысл сравнивать. Цифры оставляем: «12» —
    это выдержка, самый различающий признак на всей этикетке."""
    words = re.split(r"[^0-9a-zA-Zа-яёА-ЯЁ]+", (text or "").casefold())
    return {w for w in words if len(w) > 1 and w not in LABEL_NOISE}


def match_label(text: str, limit: int = 3) -> list[tuple[sqlite3.Row, float]]:
    """Что из справочника похоже на прочитанное с этикетки.

    Возвращает пары (запись, доля совпавших слов названия), от лучшей к худшей;
    доля 1.0 означает, что на этикетке нашлись все слова названия.

    Зачем это вообще. Раньше фотография сразу уходила в языковую модель, и
    справочник — 132 выверенных записи, среди которых ровно те бутылки, что
    и ставят на стол, — не участвовал никак. Модель отвечала по памяти: живой
    случай 6 августа — «The Macallan 12» опознан неверно и с ценой 25 000 ₽,
    при том что в справочнике он есть, с ценой 12 000 ₽. Своё знание надёжнее
    чужой памяти, бесплатно и мгновенно.
    """
    found = _label_tokens(text)
    if not found:
        return []
    scored = []
    for row in list_whiskies():
        wanted = _label_tokens(row["name"])
        if not wanted:
            continue
        hits = wanted & found
        # Одного слова мало: «12» на этикетке есть у половины справочника.
        # Названия из одного слова («Jameson») — исключение, там больше нечему
        # совпадать, но и ноль совпадений кандидатом не считается никогда.
        if not hits or (len(hits) < 2 and len(wanted) > 1):
            continue
        scored.append((row, len(hits) / len(wanted), len(hits)))
    # Сначала по доле совпадения, при равной доле — по числу совпавших слов:
    # «Macallan 12 Double Cask» точнее, чем просто «Macallan 12».
    scored.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return [(row, share) for row, share, _ in scored[:limit]]


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


def whisky_by_name(name: str) -> sqlite3.Row | None:
    """Запись с таким же названием — или None.

    Ловушка, ради которой это написано: два одинаковых названия в справочнике
    неразличимы в списке ответов. Гость видит «Talisker 10» дважды, выбирает
    не тот и получает ноль за верно названный виски. Сам он объяснить это
    не сможет, а ведущий — тем более.

    Сравниваем в Python: LIKE и COLLATE NOCASE в SQLite знают только латиницу,
    и «Талискер» с «талискер» для них разные строки.
    """
    wanted = " ".join((name or "").split()).casefold()
    if not wanted:
        return None
    with connect() as conn:
        rows = conn.execute("SELECT * FROM whisky").fetchall()
    for row in rows:
        if " ".join((row["name"] or "").split()).casefold() == wanted:
            return row
    return None


def whisky_usage(whisky_id: int) -> list[str]:
    """Названия дегустаций, где этот виски налит или назван в ответе.

    Пустой список означает «запись ни к чему не привязана, удалять безопасно».
    Смотрим и состав, и ответы: виски могли убрать из состава уже после того,
    как кто-то его назвал, — такая запись всё равно нужна, иначе в разборе
    ответов на месте названия окажется дырка.
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT t.title FROM tasting t"
            " WHERE EXISTS (SELECT 1 FROM tasting_whisky tw"
            "               WHERE tw.tasting_id = t.id AND tw.whisky_id = ?)"
            "    OR EXISTS (SELECT 1 FROM answer a"
            "               JOIN participant p ON p.id = a.participant_id"
            "               WHERE p.tasting_id = t.id AND a.whisky_id = ?)",
            (whisky_id, whisky_id),
        ).fetchall()
    return [row["title"] for row in rows]


def delete_whisky(whisky_id: int) -> None:
    """Убрать запись из справочника.

    Отказываемся, если виски участвует в дегустации: на него ссылаются состав
    и ответы, внешние ключи стоят на ON DELETE RESTRICT, и без этой проверки
    человек получил бы вместо объяснения ошибку базы. Прошлый вечер должен
    оставаться читаемым — итоги считаются из ответов заново.
    """
    used = whisky_usage(whisky_id)
    if used:
        raise ValueError(
            "Виски участвует в дегустации (" + ", ".join(used) + ") — удалить нельзя. "
            "Уберите его из состава, если вечер ещё не начался."
        )
    with connect() as conn:
        conn.execute("DELETE FROM whisky WHERE id = ?", (whisky_id,))


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


MAX_CONTACT_LENGTH = 120


def register_participant(
    tasting_id: int, name: str, contact: str = "", by_host: bool = False
) -> str:
    """Записать гостя и вернуть его личный токен.

    Токен — и адрес личной страницы, и полезная нагрузка deep link'а телеграма,
    по которой бот понимает, кого привязывает.

    Контакт необязательный и никак не проверяется: он нужен ведущему, чтобы
    было куда переслать личную ссылку, если гость её потеряет.

    by_host снимает проверку статуса, и только её. Публичная ссылка после
    начала раундов закрыта намеренно — случайный человек не должен вписаться
    в идущую дегустацию. Но опоздавший на вечеринке — это правило, а не
    исключение, и до сих пор он оставался за бортом совсем: другого пути
    внутрь не было ни у него, ни у ведущего. Теперь есть, и решает ведущий.
    """
    clean = " ".join(name.split())
    if not clean:
        raise ValueError("нужно имя")
    if len(clean) > 60:
        raise ValueError("имя слишком длинное")
    contact = " ".join(contact.split())[:MAX_CONTACT_LENGTH]

    tasting = get_tasting(tasting_id)
    if tasting is None:
        raise ValueError("дегустация не найдена")
    if tasting["status"] in RESULT_STATUSES:
        # Итоги уже посчитаны: запись сюда — это участник с нулём и без
        # единого раунда. Ему нужна следующая дегустация, а не эта.
        raise ValueError("дегустация уже закончена")
    if not by_host and tasting["status"] != "registration":
        raise ValueError("регистрация на эту дегустацию сейчас закрыта")

    token = secrets.token_urlsafe(16)
    with connect() as conn:
        conn.execute(
            "INSERT INTO participant (tasting_id, name, join_token, contact)"
            " VALUES (?, ?, ?, ?)",
            (tasting_id, clean, token, contact or None),
        )
    return token


def carry_over_telegram(previous_id: int, participant_id: int) -> bool:
    """Перенести привязку телеграма со старой записи участника на новую.

    Гость, который приходит второй раз, уже проходил всю возню с ботом.
    Заставлять его повторять её — единственное, что он запомнит о вечере.

    Переносим только с той записи, которую этот же телефон открывал раньше:
    доверять полю «куда прислать» тут нельзя, туда можно вписать чужой ник,
    и итоги ушли бы постороннему человеку.
    """
    with connect() as conn:
        previous = conn.execute(
            "SELECT tg_chat_id, tg_username, contact FROM participant WHERE id = ?",
            (previous_id,),
        ).fetchone()
        if previous is None or previous["tg_chat_id"] is None:
            return False
        conn.execute(
            "UPDATE participant SET tg_chat_id = ?, tg_username = ?,"
            " contact = COALESCE(NULLIF(contact, ''), ?)"
            " WHERE id = ? AND tg_chat_id IS NULL",
            (previous["tg_chat_id"], previous["tg_username"], previous["contact"], participant_id),
        )
        return True


def matching_telegram(tasting_id: int, participant_id: int) -> sqlite3.Row | None:
    """Тот же человек на прошлой дегустации — по контакту или нику в телеграме.

    Только подсказка ведущему: связывать по совпадению строки автоматически
    нельзя, контакт пишет сам гость и может ошибиться или указать чужой.
    """
    with connect() as conn:
        me = conn.execute(
            "SELECT contact, tg_chat_id FROM participant WHERE id = ?", (participant_id,)
        ).fetchone()
        if me is None or me["tg_chat_id"] is not None:
            return None
        needle = (me["contact"] or "").strip().lstrip("@").casefold()
        if not needle:
            return None
        for row in conn.execute(
            "SELECT p.*, t.title FROM participant p JOIN tasting t ON t.id = p.tasting_id"
            " WHERE p.tg_chat_id IS NOT NULL AND p.tasting_id != ? ORDER BY p.id DESC",
            (tasting_id,),
        ):
            candidates = {
                (row["contact"] or "").strip().lstrip("@").casefold(),
                (row["tg_username"] or "").strip().lstrip("@").casefold(),
            }
            if needle in candidates - {""}:
                return row
    return None


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


# ── раунды ─────────────────────────────────────────────────────────────────

ROUND_TITLES = {"nose": "по запаху", "palate": "по вкусу"}

# Раунд определяется статусом дегустации, а не приходит из формы: иначе
# участник мог бы отвечать во втором раунде, пока идёт первый.
ROUND_BY_STATUS = {"round_nose": "nose", "round_palate": "palate"}

MAX_TAGS_LENGTH = 200

# Класс (или регион) в ответе — это выбор из выпадающего списка, но приходит
# он тем же POST, что и всё остальное, и прислать туда можно что угодно любой
# длины. Самое длинное настоящее значение — 28 символов («односолодовый
# (не Шотландия)»), самый длинный регион справочника — 13. Потолок с большим
# запасом: он не отбирает ни одного честного ответа и не даёт залить в базу
# мегабайт текста на каждый образец.
MAX_CATEGORY_LENGTH = 60


def open_round(tasting: sqlite3.Row) -> str | None:
    return ROUND_BY_STATUS.get(tasting["status"])


def round_choices(tasting_id: int) -> list[sqlite3.Row]:
    """Названия для выпадающего списка — по алфавиту.

    По умолчанию это весь справочник: тогда назвать можно и то, чего на столе
    нет, и частичный балл за класс перестаёт быть формальностью. Режим
    'tasting' сужает список до налитого — так проще, но и скучнее.

    Сознательно не в порядке номеров образцов: список, идущий в том же порядке,
    что и стаканы, сам по себе был бы ответом. Сортировка — через by_name(),
    иначе кириллица встаёт вперемешку (см. там же).
    """
    tasting = get_tasting(tasting_id)
    if tasting is None:
        return []
    if tasting["answer_scope"] == "tasting":
        with connect() as conn:
            return by_name(
                conn.execute(
                    # region нужен для группировки списка на дегустации
                    # по регионам — без него все варианты сваливаются
                    # в одну группу «без региона».
                    "SELECT w.id, w.name, w.wclass, w.region FROM tasting_whisky tw"
                    " JOIN whisky w ON w.id = tw.whisky_id"
                    " WHERE tw.tasting_id = ?",
                    (tasting_id,),
                ).fetchall()
            )
    return list_whiskies()


NO_CATEGORY = "без региона"


def grouped_choices(rows, level: str = "class") -> list[tuple[str, list]]:
    """Те же варианты, разложенные на группы — для <optgroup>.

    Справочник разросся до сотни с лишним названий, и плоский список стал
    свитком: гость крутит его в темноте, с бокалом в руке. Разложенный
    по группам он листается глазами.

    Группы — по тому, за что даётся частичный балл (docs/SCORING.md), а это
    зависит от дегустации. Пока здесь всегда стояли классы, дегустация
    по регионам получалась злой: гостю написано «не угадали розлив —
    называйте похожий», похожий здесь значит «того же региона», а список
    разложен по классам, и найти в нём соседа по региону нельзя никак.

    Порядок классов — как в WHISKY_CLASSES, а не по алфавиту: скотч сверху,
    «прочее» в конце. Регионы по алфавиту, а «без региона» — последним:
    там купажи, у которых региона нет по существу.
    """
    field = "region" if level == "region" else "wclass"
    default = NO_CATEGORY if level == "region" else "прочее"
    buckets: dict[str, list] = {}
    for row in rows:
        value = ((row[field] if field in row.keys() else None) or "").strip() or default
        buckets.setdefault(value, []).append(row)
    if level == "region":
        rest = buckets.pop(NO_CATEGORY, None)
        groups = sorted(buckets.items(), key=lambda pair: pair[0].casefold())
        return groups + ([(NO_CATEGORY, rest)] if rest else [])
    known = [(c, buckets.pop(c)) for c in WHISKY_CLASSES if c in buckets]
    # Класс, которого нет в словаре, — заведён руками до того, как список
    # устоялся. Не теряем его: без группы виски пропал бы из вариантов ответа.
    return known + sorted(buckets.items())


def sample_numbers(tasting_id: int) -> list[int]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT sample_no FROM tasting_whisky WHERE tasting_id = ? ORDER BY sample_no",
            (tasting_id,),
        ).fetchall()
    return [row["sample_no"] for row in rows]


def get_answers(participant_id: int, round_name: str) -> dict[int, int]:
    """Черновик или отправленный ответ: номер образца → id виски."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT sample_no, whisky_id FROM answer WHERE participant_id = ? AND round = ?",
            (participant_id, round_name),
        ).fetchall()
    return {row["sample_no"]: row["whisky_id"] for row in rows}


def round_submitted(participant_id: int, round_name: str) -> bool:
    """Заморожен ли ответ. Смотрим обе таблицы, и это не формальность.

    Ответ бывает и без единого названия — когда гость назвал только класс
    (или регион). Пока сюда смотрела одна таблица answer, такой гость после
    «Отправить» видел форму заново, будто ничего не сохранилось, а админка
    показывала «сдали 0».
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM answer"
            " WHERE participant_id = ? AND round = ? AND submitted_at IS NOT NULL"
            " UNION ALL"
            " SELECT 1 FROM answer_category"
            " WHERE participant_id = ? AND round = ? AND submitted_at IS NOT NULL"
            " LIMIT 1",
            (participant_id, round_name, participant_id, round_name),
        ).fetchone()
    return row is not None


def get_ratings(participant_id: int) -> dict[int, sqlite3.Row]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM rating WHERE participant_id = ?", (participant_id,)
        ).fetchall()
    return {row["sample_no"]: row for row in rows}


def save_round_draft(
    participant_id: int,
    round_name: str,
    answers: dict[int, int | None],
    scores: dict[int, int | None] | None = None,
    tags: dict[int, str] | None = None,
    categories: dict[int, str] | None = None,
) -> None:
    """Сохранить черновик раунда целиком.

    Ответы переписываются целиком, а не по одному: так не нужно бороться
    с UNIQUE при перестановке двух названий местами — обычное дело, когда
    участник передумал.
    """
    if round_submitted(participant_id, round_name):
        raise ValueError("ответ уже отправлен, править нельзя")

    tasting_id = _tasting_of(participant_id)
    valid_samples = set(sample_numbers(tasting_id))
    valid_whiskies = {row["id"] for row in round_choices(tasting_id)}

    chosen: dict[int, int] = {}
    for sample_no, whisky_id in answers.items():
        if whisky_id is None:
            continue
        if sample_no not in valid_samples:
            raise ValueError(f"нет образца №{sample_no}")
        if whisky_id not in valid_whiskies:
            raise ValueError("этого виски нет в составе дегустации")
        chosen[sample_no] = whisky_id
    if len(set(chosen.values())) != len(chosen):
        raise ValueError("одно название нельзя поставить двум образцам")

    with connect() as conn:
        conn.execute(
            "DELETE FROM answer WHERE participant_id = ? AND round = ?",
            (participant_id, round_name),
        )
        conn.executemany(
            "INSERT INTO answer (participant_id, round, sample_no, whisky_id) VALUES (?, ?, ?, ?)",
            [(participant_id, round_name, no, wid) for no, wid in chosen.items()],
        )
        _save_ratings(conn, participant_id, round_name, valid_samples, scores or {}, tags or {})
        _save_categories(conn, participant_id, round_name, valid_samples, categories or {})


def _save_categories(conn, participant_id, round_name, valid_samples, categories) -> None:
    """Ответ «а какой это хотя бы класс» — отдельно от названия.

    Он даёт тот же частичный балл, что и виски угаданного класса, и нужен
    тому, кто уверен в классе, но не помнит ни одной винокурни в нём.
    Переписываем целиком, как и названия: черновик правят до последнего.
    """
    conn.execute(
        "DELETE FROM answer_category WHERE participant_id = ? AND round = ?",
        (participant_id, round_name),
    )
    rows = [
        (participant_id, round_name, no, value.strip()[:MAX_CATEGORY_LENGTH])
        for no, value in categories.items()
        if no in valid_samples and (value or "").strip()
    ]
    conn.executemany(
        "INSERT INTO answer_category (participant_id, round, sample_no, category)"
        " VALUES (?, ?, ?, ?)",
        rows,
    )


def get_categories(participant_id: int, round_name: str) -> dict[int, str]:
    """Что участник назвал классом (или регионом) в этом раунде."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT sample_no, category FROM answer_category"
            " WHERE participant_id = ? AND round = ?",
            (participant_id, round_name),
        ).fetchall()
    return {int(r["sample_no"]): r["category"] for r in rows}


def _save_ratings(conn, participant_id, round_name, valid_samples, scores, tags) -> None:
    """Личные оценки и теги. В зачёт не идут — это память о вечере.

    Теги хранятся по раундам в одном JSON: по запаху и по вкусу они разные,
    а строка в таблице на образец одна.
    """
    touched = set(scores) | set(tags)
    for sample_no in touched:
        if sample_no not in valid_samples:
            continue
        row = conn.execute(
            "SELECT score, scores, tags FROM rating"
            " WHERE participant_id = ? AND sample_no = ?",
            (participant_id, sample_no),
        ).fetchone()
        stored_tags = _json_map(row["tags"] if row else None)
        stored_scores = _json_map(row["scores"] if row else None)
        if sample_no in tags:
            stored_tags[round_name] = tags[sample_no][:MAX_TAGS_LENGTH]
        if sample_no in scores and scores[sample_no] is not None:
            # Бегунок ходит от 0 до 100, но приходит оценка обычным полем
            # формы, и прислать туда можно любое число. По этим оценкам
            # выбирается «виски вечера»: без потолка один гость с консолью
            # в браузере назначает победителя вечера в одиночку.
            stored_scores[round_name] = max(0, min(100, scores[sample_no]))
        # score — последнее осознанное мнение: вкус, если он есть. По нему
        # считается «виски вечера», и запрос за ним переписывать незачем.
        # Строки, заведённые до разделения оценок по раундам, знают только
        # score — его и оставляем, иначе правка тегов молча обнулит оценку.
        latest = stored_scores.get("palate", stored_scores.get("nose"))
        if latest is None and row is not None:
            latest = row["score"]
        conn.execute(
            "INSERT INTO rating (participant_id, sample_no, score, scores, tags)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT (participant_id, sample_no)"
            " DO UPDATE SET score = excluded.score, scores = excluded.scores,"
            "               tags = excluded.tags",
            (
                participant_id,
                sample_no,
                latest,
                json.dumps(stored_scores, ensure_ascii=False),
                json.dumps(stored_tags, ensure_ascii=False),
            ),
        )


def _json_map(raw) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def get_scores(participant_id: int, round_name: str) -> dict[int, int]:
    """Оценки этого раунда. Пусто — бегунок стоит посередине, как в начале."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT sample_no, scores FROM rating WHERE participant_id = ?",
            (participant_id,),
        ).fetchall()
    result = {}
    for row in rows:
        value = _json_map(row["scores"]).get(round_name)
        if value is not None:
            result[int(row["sample_no"])] = int(value)
    return result


def submit_round(participant_id: int, round_name: str) -> None:
    """Заморозить ответ. После этого править нельзя — в этом и смысл кнопки."""
    if round_submitted(participant_id, round_name):
        raise ValueError("ответ уже отправлен")
    tasting_id = _tasting_of(participant_id)
    total = len(sample_numbers(tasting_id))
    # Образец считается отвеченным, если названо хоть что-то: розлив или
    # класс. Пока сюда смотрели только названия, гость, ответивший одними
    # классами, получал «заполнено 0 из 3» и не мог отправить ответ вовсе —
    # при том что баллы за эти классы начислялись.
    filled = set(get_answers(participant_id, round_name)) | set(
        get_categories(participant_id, round_name)
    )
    if len(filled) < total:
        raise ValueError(f"заполнено {len(filled)} из {total} — ответьте на все образцы")
    with connect() as conn:
        for table in ("answer", "answer_category"):
            conn.execute(
                f"UPDATE {table} SET submitted_at = CURRENT_TIMESTAMP"
                " WHERE participant_id = ? AND round = ?",
                (participant_id, round_name),
            )


def round_progress(tasting_id: int, round_name: str) -> tuple[int, int]:
    """Сколько человек сдали ответ и сколько всего записалось."""
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total,"
            "       (SELECT COUNT(DISTINCT id) FROM ("
            "          SELECT a.participant_id AS id FROM answer a"
            "            JOIN participant p2 ON p2.id = a.participant_id"
            "           WHERE p2.tasting_id = ? AND a.round = ? AND a.submitted_at IS NOT NULL"
            "          UNION"
            "          SELECT c.participant_id FROM answer_category c"
            "            JOIN participant p3 ON p3.id = c.participant_id"
            "           WHERE p3.tasting_id = ? AND c.round = ? AND c.submitted_at IS NOT NULL"
            "       )) AS done"
            " FROM participant WHERE tasting_id = ?",
            (tasting_id, round_name, tasting_id, round_name, tasting_id),
        ).fetchone()
    return int(row["done"] or 0), int(row["total"] or 0)


def answer_status(tasting_id: int) -> dict[int, dict[str, str]]:
    """Что каждый гость сдал по каждому раунду: отправлено / черновик / ничего.

    Счётчик «сдали N из M» показывает только идущий раунд и исчезает, когда
    раунды кончились. На живой дегустации из-за этого было не понять, сдал ли
    человек вкус: карточка раунда уже пропала, а других следов на странице нет.
    Здесь состояние по обоим раундам, и видно оно в любой момент вечера.
    """
    # Обе таблицы: ответ бывает и без единого названия — одними классами.
    with connect() as conn:
        rows = conn.execute(
            "SELECT p.id, a.round,"
            "       MAX(CASE WHEN a.submitted_at IS NOT NULL THEN 1 ELSE 0 END) AS sent,"
            "       COUNT(a.round) AS answers"
            " FROM participant p LEFT JOIN ("
            "        SELECT participant_id, round, submitted_at FROM answer"
            "        UNION ALL"
            "        SELECT participant_id, round, submitted_at FROM answer_category"
            "      ) a ON a.participant_id = p.id"
            " WHERE p.tasting_id = ?"
            " GROUP BY p.id, a.round",
            (tasting_id,),
        ).fetchall()
    status: dict[int, dict[str, str]] = {}
    for row in rows:
        person = status.setdefault(int(row["id"]), {})
        if row["round"] is None:
            continue
        if row["sent"]:
            person[row["round"]] = "отправлен"
        elif row["answers"]:
            person[row["round"]] = "черновик"
    return status


# ── итоги ──────────────────────────────────────────────────────────────────

RESULT_STATUSES = {"scoring", "closed"}


def tasting_truth(tasting_id: int) -> dict[int, int]:
    """Что налито на самом деле: номер образца → id виски."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT sample_no, whisky_id FROM tasting_whisky WHERE tasting_id = ?",
            (tasting_id,),
        ).fetchall()
    return {row["sample_no"]: row["whisky_id"] for row in rows}


def whisky_categories(tasting_id: int, level: str) -> dict[int, str | None]:
    """Категория каждого виски — по классу или по региону.

    Берём весь справочник, а не только налитое: назвать можно любой виски,
    и частичный балл считается по классу названного, каким бы он ни был.
    Аргумент tasting_id остаётся ради читаемости вызова.
    """
    column = "region" if level == "region" else "wclass"
    with connect() as conn:
        rows = conn.execute(f"SELECT id, {column} AS value FROM whisky").fetchall()
    return {row["id"]: row["value"] for row in rows}


def category_choices(level: str) -> list[str]:
    """Из чего гость выбирает класс (или регион) напрямую.

    Классы — фиксированный список из кода. Регионы фиксировать нельзя: их
    столько, сколько заведено в справочнике, и они меняются вместе с ним, —
    поэтому собираем из данных.
    """
    if level != "region":
        return list(WHISKY_CLASSES)
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT region FROM whisky WHERE region IS NOT NULL AND region != ''"
        ).fetchall()
    return sorted((row["region"] for row in rows), key=str.casefold)


def palate_finished_at(tasting_id: int) -> dict[int, str | None]:
    """Когда участник отправил второй раунд — это последний тай-брейк.

    Обе таблицы: ответ бывает и без единого названия, одними классами. Пока
    смотрели в одну, такой участник выглядел как «не отправлял вовсе» и при
    равенстве очков всегда оказывался ниже — за то, чего не делал.
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT a.participant_id, MAX(a.submitted_at) AS at FROM ("
            "   SELECT participant_id, round, submitted_at FROM answer"
            "   UNION ALL"
            "   SELECT participant_id, round, submitted_at FROM answer_category"
            " ) a"
            " JOIN participant p ON p.id = a.participant_id"
            " WHERE p.tasting_id = ? AND a.round = 'palate'"
            " GROUP BY a.participant_id",
            (tasting_id,),
        ).fetchall()
    return {row["participant_id"]: row["at"] for row in rows}


def score_tasting(tasting_id: int) -> dict[int, scoring.Score]:
    """Посчитать очки всех участников. Базу не меняет — только читает."""
    tasting = get_tasting(tasting_id)
    if tasting is None:
        raise ValueError("дегустация не найдена")
    truth = tasting_truth(tasting_id)
    categories = whisky_categories(tasting_id, tasting["category_level"])
    return {
        person["id"]: scoring.score_participant(
            truth,
            {
                "nose": get_answers(person["id"], "nose"),
                "palate": get_answers(person["id"], "palate"),
            },
            categories,
            {
                "nose": get_categories(person["id"], "nose"),
                "palate": get_categories(person["id"], "palate"),
            },
        )
        for person in list_participants(tasting_id)
    }


def compute_results(tasting_id: int) -> None:
    """Пересчитать таблицу итогов целиком.

    `result` — кэш, а не источник истины: строки удаляются и пишутся заново,
    поэтому кнопку «пересчитать» можно жать сколько угодно раз.
    """
    scores = score_tasting(tasting_id)
    places = dict(scoring.rank(scores, palate_finished_at(tasting_id)))
    with connect() as conn:
        conn.execute(
            "DELETE FROM result WHERE participant_id IN"
            " (SELECT id FROM participant WHERE tasting_id = ?)",
            (tasting_id,),
        )
        conn.executemany(
            "INSERT INTO result (participant_id, points_nose, points_palate,"
            " points_partial, points_bonus, total, place, computed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            [
                (
                    participant_id,
                    score.points_nose,
                    score.points_palate,
                    score.points_partial,
                    score.points_bonus,
                    score.total,
                    places[participant_id],
                )
                for participant_id, score in scores.items()
            ],
        )


def leaderboard(tasting_id: int) -> list[sqlite3.Row]:
    """Турнирная таблица. Пустая, пока итоги не посчитаны."""
    with connect() as conn:
        return conn.execute(
            "SELECT p.id, p.name, p.tg_chat_id, r.* FROM participant p"
            " JOIN result r ON r.participant_id = p.id"
            " WHERE p.tasting_id = ? ORDER BY r.place, p.name COLLATE NOCASE",
            (tasting_id,),
        ).fetchall()


def personal_result(participant_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM result WHERE participant_id = ?", (participant_id,)
        ).fetchone()


def sample_breakdown(tasting_id: int) -> list[dict]:
    """Разбор по образцам: что это было, кто угадал, как оценили."""
    truth = tasting_truth(tasting_id)
    whiskies = {row["id"]: row for row in tasting_whiskies(tasting_id)}
    people = {person["id"]: person["name"] for person in list_participants(tasting_id)}
    scores = score_tasting(tasting_id)
    averages = average_scores(tasting_id)

    rows = []
    for sample_no in sorted(truth):
        guessed = {"nose": [], "palate": []}
        for participant_id, score in scores.items():
            for result in score.samples:
                if result.sample_no != sample_no:
                    continue
                if result.nose_id == result.truth_id:
                    guessed["nose"].append(people[participant_id])
                if result.palate_id == result.truth_id:
                    guessed["palate"].append(people[participant_id])
        rows.append(
            {
                "sample_no": sample_no,
                "whisky": whiskies.get(truth[sample_no]),
                "nose": sorted(guessed["nose"]),
                "palate": sorted(guessed["palate"]),
                "average": averages.get(sample_no),
            }
        )
    return rows


def average_scores(tasting_id: int) -> dict[int, float]:
    """Средняя личная оценка образца — по ней выбирается «виски вечера»."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT r.sample_no, AVG(r.score) AS avg_score FROM rating r"
            " JOIN participant p ON p.id = r.participant_id"
            " WHERE p.tasting_id = ? AND r.score IS NOT NULL"
            " GROUP BY r.sample_no",
            (tasting_id,),
        ).fetchall()
    return {row["sample_no"]: round(row["avg_score"], 1) for row in rows}


def whisky_of_the_night(tasting_id: int) -> dict | None:
    """Образец с самой высокой средней оценкой. None, если никто не оценивал."""
    averages = average_scores(tasting_id)
    if not averages:
        return None
    sample_no = max(averages, key=lambda no: averages[no])
    truth = tasting_truth(tasting_id)
    whiskies = {row["id"]: row for row in tasting_whiskies(tasting_id)}
    return {
        "sample_no": sample_no,
        "average": averages[sample_no],
        "whisky": whiskies.get(truth.get(sample_no)),
    }


# ── отметки о доставке ─────────────────────────────────────────────────────


def delivered(tasting_id: int, kind: str) -> set[int]:
    """Кому это сообщение уже уходило."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT d.participant_id FROM delivery d"
            " JOIN participant p ON p.id = d.participant_id"
            " WHERE p.tasting_id = ? AND d.kind = ?",
            (tasting_id, kind),
        ).fetchall()
    return {row["participant_id"] for row in rows}


def mark_delivered(participant_id: int, kind: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO delivery (participant_id, kind) VALUES (?, ?)",
            (participant_id, kind),
        )


def _tasting_of(participant_id: int) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT tasting_id FROM participant WHERE id = ?", (participant_id,)
        ).fetchone()
    if row is None:
        raise ValueError("участник не найден")
    return int(row["tasting_id"])


def _require_editable(tasting_id: int) -> None:
    tasting = get_tasting(tasting_id)
    if tasting is None:
        raise ValueError("дегустация не найдена")
    if tasting["status"] not in EDITABLE_STATUSES:
        raise ValueError(
            "состав нельзя менять после начала раундов "
            f"(статус: {STATUS_TITLES.get(tasting['status'], tasting['status'])})"
        )
