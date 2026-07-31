"""Распознавание виски по названию или по фотографии бутылки.

Почему модель, а не справочник: публичных каталогов с нотами вкуса, которые
разрешено показывать на своём сайте, нет — Whiskybase и Whiskystats это прямо
запрещают, у WHISKY:EDITION открытая лицензия, но всего ~500 записей.
Подробности и проверка — в docs/PLAN.md.

Ответы кэшируются в таблице ai_cache: повторный запрос того же виски не идёт
в API и ничего не стоит.
"""

import hashlib
import json
import logging
import os
import time

from app.db import connect

log = logging.getLogger("str1.ai")

MODEL = "claude-opus-5"

# Ограничение частоты: сколько запросов к модели можно сделать с одного адреса
# за час. Счётчик в памяти процесса — приложение одно, этого достаточно.
RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 3600
_requests: dict[str, list[float]] = {}

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Все поля строковые намеренно: числа приходят от модели в разном виде
# («40», «40 %», «41,5»), и разбираются они там же, где данные из форм админки.
CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "recognized": {
            "type": "boolean",
            "description": "Удалось ли опознать конкретный виски",
        },
        "name": {"type": "string", "description": "Полное название, как на этикетке"},
        "distillery": {"type": "string"},
        "wclass": {
            "type": "string",
            "description": "односолодовый скотч, купажированный скотч, бурбон, ржаной или прочее",
        },
        "region": {"type": "string", "description": "Регион или штат, пустая строка если нет"},
        "abv": {"type": "string", "description": "Крепость в процентах, только число"},
        "age_years": {"type": "string", "description": "Выдержка в годах, только число; пусто если NAS"},
        "cask": {"type": "string", "description": "Типы бочек"},
        "grain": {"type": "string", "description": "Сырьё"},
        "filtration": {"type": "string", "description": "Холодная фильтрация: да, нет или неизвестно"},
        "price_rub": {"type": "string", "description": "Ориентировочная розничная цена в рублях, только число"},
        "colour": {"type": "string"},
        "nose": {"type": "string", "description": "Аромат, одно-два предложения"},
        "palate": {"type": "string", "description": "Вкус, одно-два предложения"},
        "finish": {"type": "string", "description": "Послевкусие, одно-два предложения"},
        "confidence": {"type": "string", "enum": ["высокая", "средняя", "низкая"]},
        "comment": {
            "type": "string",
            "description": "Что видно на фото или почему не удалось опознать. Пусто, если всё понятно.",
        },
    },
    "required": [
        "recognized", "name", "distillery", "wclass", "region", "abv", "age_years",
        "cask", "grain", "filtration", "price_rub", "colour", "nose", "palate",
        "finish", "confidence", "comment",
    ],
    "additionalProperties": False,
}

SYSTEM = (
    "Ты помогаешь гостям дегустации разобраться в виски. Отвечай по-русски, "
    "коротко и по делу, без рекламных оборотов.\n"
    "Заполняй только то, в чём уверен: неизвестное поле оставляй пустой строкой, "
    "не выдумывай. Цену указывай как ориентир для российской розницы.\n"
    "Если опознать конкретный розлив не удалось, ставь recognized=false и объясняй "
    "в comment, что мешает."
)


class AiUnavailable(Exception):
    """Модель недоступна: нет ключа, сбой сети или отказ API."""


class RateLimited(Exception):
    """Слишком часто с одного адреса."""


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def check_rate_limit(ip: str) -> None:
    now = time.time()
    recent = [t for t in _requests.get(ip, []) if now - t < RATE_WINDOW_SECONDS]
    _requests[ip] = recent
    if len(recent) >= RATE_LIMIT:
        raise RateLimited
    recent.append(now)


def lookup_by_name(query: str) -> dict:
    """Карточка по названию. Результат кэшируется по нормализованному запросу."""
    key = "name:" + " ".join(query.split()).casefold()
    cached = _from_cache(key)
    if cached is not None:
        return cached

    card = _ask(
        [
            {
                "role": "user",
                "content": (
                    f"Что это за виски: «{query}»? Заполни карточку.\n"
                    "Если под это название подходит несколько розливов, возьми самый "
                    "распространённый и скажи об этом в comment."
                ),
            }
        ]
    )
    _to_cache(key, "text", card)
    return card


def lookup_by_photo(image_bytes: bytes, media_type: str) -> dict:
    """Карточка по фотографии бутылки. Кэш — по хешу самого изображения."""
    if media_type not in ALLOWED_IMAGE_TYPES:
        raise AiUnavailable("Такой формат изображения не поддерживается: нужен JPEG, PNG или WebP.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise AiUnavailable("Фотография слишком большая: до 5 МБ.")

    key = "image:" + hashlib.sha256(image_bytes).hexdigest()
    cached = _from_cache(key)
    if cached is not None:
        return cached

    import base64

    card = _ask(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.standard_b64encode(image_bytes).decode("ascii"),
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Что за виски на фотографии? Заполни карточку.\n"
                            "Если бутылки не видно или этикетка нечитаема, поставь "
                            "recognized=false и напиши в comment, что именно видно."
                        ),
                    },
                ],
            }
        ]
    )
    _to_cache(key, "image", card)
    return card


def _ask(messages: list[dict]) -> dict:
    """Единственное место, где происходит обращение к API. Тесты подменяют его."""
    if not is_configured():
        raise AiUnavailable("Распознавание выключено: на сервере не задан ANTHROPIC_API_KEY.")

    try:
        import anthropic
    except ImportError as err:  # pragma: no cover — на сервере пакет стоит всегда
        raise AiUnavailable("Библиотека anthropic не установлена.") from err

    client = anthropic.Anthropic(timeout=60.0, max_retries=1)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM,
            messages=messages,
            # Строгая схема: ответ гарантированно разбирается, а не «почти JSON».
            output_config={
                "format": {"type": "json_schema", "schema": CARD_SCHEMA},
                # Задача несложная, глубокие размышления тут только жгут токены.
                "effort": "low",
            },
        )
    except Exception as err:
        # Полная трасса уходит в журнал службы (journalctl -u str-1-app),
        # на странице показываем короткую причину: без неё «попробуйте ещё раз»
        # ничего не говорит ни гостю, ни тому, кто чинит. Ключ в текст ошибок
        # Anthropic не попадает.
        log.exception("запрос к модели не удался")
        reason = f"{type(err).__name__}: {err}"
        # 403 «Request not allowed» приходит с края сети, до проверки ключа:
        # так Anthropic отвечает на запросы из регионов, где API не работает.
        # Наш сервер в Москве, поэтому распознавание отсюда невозможно —
        # см. docs/PLAN.md, шаг 4. Неверный ключ выглядел бы иначе: 401.
        if "403" in reason and "not allowed" in reason.lower():
            raise AiUnavailable(
                "Распознавание недоступно: сервер находится в регионе, откуда "
                "Anthropic API не обслуживается. Ключ здесь ни при чём."
            ) from err
        raise AiUnavailable(f"Не удалось получить ответ модели. {reason[:300]}") from err

    if response.stop_reason == "refusal":
        raise AiUnavailable("Модель отказалась отвечать на этот запрос.")

    text = next((block.text for block in response.content if block.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise AiUnavailable("Модель вернула неразборчивый ответ.") from err


# ── кэш ────────────────────────────────────────────────────────────────────


def _from_cache(key: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT payload FROM ai_cache WHERE key = ?", (key,)).fetchone()
    return json.loads(row["payload"]) if row else None


def _to_cache(key: str, kind: str, card: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (key, kind, payload) VALUES (?, ?, ?)",
            (key, kind, json.dumps(card, ensure_ascii=False)),
        )


def cached_card(key: str) -> dict | None:
    """Достать карточку по ключу кэша — нужно админке, чтобы её сохранить."""
    return _from_cache(key)


def cache_key_for_name(query: str) -> str:
    return "name:" + " ".join(query.split()).casefold()


def cache_key_for_image(image_bytes: bytes) -> str:
    return "image:" + hashlib.sha256(image_bytes).hexdigest()
