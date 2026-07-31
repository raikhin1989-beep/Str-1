"""Распознавание виски по названию или по фотографии бутылки.

Почему модель, а не справочник: публичных каталогов с нотами вкуса, которые
разрешено показывать на своём сайте, нет — Whiskybase и Whiskystats это прямо
запрещают, у WHISKY:EDITION открытая лицензия, но всего ~500 записей.
Подробности и проверка — в docs/PLAN.md.

Провайдеров два, выбор — в app/config.ai_provider():

* **yandex** — Yandex AI Studio. Работает с сервера в России, поэтому сейчас
  основной. Текст обрабатывает yandexgpt, фотографии — gemma-3-27b-it.
* **anthropic** — как задумывалось изначально. С московского сервера получает
  403 ещё на краю сети, поэтому включится только после переезда хостинга.

Ответы кэшируются в таблице ai_cache: повторный запрос того же виски не идёт
в API и ничего не стоит.
"""

import hashlib
import json
import logging
import os
import re
import time

from app.config import ai_provider, anthropic_key, yandex_folder, yandex_key
from app.db import connect

log = logging.getLogger("str1.ai")

ANTHROPIC_MODEL = "claude-opus-5"

# Yandex AI Studio, OpenAI-совместимый эндпоинт — тот же, которым пользуется
# их официальный SDK (yandex-cloud/yandex-ai-studio-sdk).
YANDEX_URL = "https://llm.api.cloud.yandex.net/v1/chat/completions"
# Список моделей, доступных каталогу. Спрашиваем только когда в доступе отказали:
# по нему сразу видно, открыта ли каталогу нужная модель вообще.
YANDEX_MODELS_URL = "https://llm.api.cloud.yandex.net/v1/models"
YANDEX_TEXT_MODEL = "yandexgpt"
# Картинки на сегодня понимает только эта модель — так прямо сказано
# в примере multimodal.py их SDK: «at this moment this is only model
# which supports image processing».
YANDEX_VISION_MODEL = "gemma-3-27b-it"

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
    return ai_provider() is not None


def provider() -> str | None:
    return ai_provider()


def supports_images() -> bool:
    """Умеет ли текущий провайдер разбирать фотографии."""
    return ai_provider() in {"anthropic", "yandex"}


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
        f"Что это за виски: «{query}»? Заполни карточку.\n"
        "Если под это название подходит несколько розливов, возьми самый "
        "распространённый и скажи об этом в comment."
    )
    _to_cache(key, "text", card)
    return card


def lookup_by_photo(image_bytes: bytes, media_type: str) -> dict:
    """Карточка по фотографии бутылки. Кэш — по хешу самого изображения."""
    if not supports_images():
        raise AiUnavailable("Распознавание по фотографии сейчас недоступно.")
    if media_type not in ALLOWED_IMAGE_TYPES:
        raise AiUnavailable("Такой формат изображения не поддерживается: нужен JPEG, PNG или WebP.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise AiUnavailable("Фотография слишком большая: до 5 МБ.")

    key = "image:" + hashlib.sha256(image_bytes).hexdigest()
    cached = _from_cache(key)
    if cached is not None:
        return cached

    card = _ask(
        "Что за виски на фотографии? Заполни карточку.\n"
        "Если бутылки не видно или этикетка нечитаема, поставь recognized=false "
        "и напиши в comment, что именно видно.",
        image=(image_bytes, media_type),
    )
    _to_cache(key, "image", card)
    return card


def _ask(prompt: str, image: tuple[bytes, str] | None = None) -> dict:
    """Единственное место, где происходит обращение к API. Тесты подменяют его."""
    chosen = ai_provider()
    if chosen is None:
        raise AiUnavailable(
            "Распознавание выключено: на сервере не заданы ключи ни Яндекса, ни Anthropic."
        )
    if chosen == "yandex":
        return _ask_yandex(prompt, image)
    return _ask_anthropic(prompt, image)


def _ask_anthropic(prompt: str, image: tuple[bytes, str] | None) -> dict:
    try:
        import anthropic
    except ImportError as err:  # pragma: no cover — на сервере пакет стоит всегда
        raise AiUnavailable("Библиотека anthropic не установлена.") from err

    content: list[dict] = []
    if image is not None:
        import base64

        image_bytes, media_type = image
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(image_bytes).decode("ascii"),
                },
            }
        )
    content.append({"type": "text", "text": prompt})

    client = anthropic.Anthropic(api_key=anthropic_key(), timeout=60.0, max_retries=1)
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
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
    return _parse_card(text)


def _ask_yandex(prompt: str, image: tuple[bytes, str] | None = None) -> dict:
    """Yandex AI Studio через OpenAI-совместимый эндпоинт.

    Тот же адрес и та же форма запроса, что у их официального SDK. Картинку
    принимает только gemma-3-27b-it, поэтому модель выбирается по наличию фото.
    """
    import base64

    import httpx

    model = YANDEX_VISION_MODEL if image is not None else YANDEX_TEXT_MODEL
    content: list[dict] = [{"type": "text", "text": prompt}]
    if image is not None:
        image_bytes, media_type = image
        encoded = base64.standard_b64encode(image_bytes).decode("ascii")
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{encoded}"}}
        )

    fields = ", ".join(CARD_SCHEMA["required"])
    payload = {
        "model": f"gpt://{yandex_folder()}/{model}/latest",
        "messages": [
            {
                "role": "system",
                "content": (
                    SYSTEM
                    + "\n\nОтвечай ТОЛЬКО объектом JSON, без пояснений и без разметки. "
                    + f"Обязательные поля: {fields}. "
                    + "Поле recognized — true или false, остальные — строки; "
                    + "неизвестное оставляй пустой строкой."
                ),
            },
            {"role": "user", "content": content},
        ],
        "max_tokens": 2000,
        "temperature": 0.3,
    }
    schema = {
        "type": "json_schema",
        "json_schema": {"name": "whisky_card", "schema": CARD_SCHEMA},
    }

    # Схему просим параметром, но не полагаемся на неё: она поддержана не всеми
    # моделями семейства, и отказ из-за неё не должен ронять распознавание.
    # Инструкция в системном сообщении и терпимый разбор работают и без неё.
    try:
        body = _yandex_post({**payload, "response_format": schema}, allow_retry=True)
        if body is None:
            body = _yandex_post(payload, allow_retry=False)
    except AiUnavailable as err:
        raise _explain_refusal(err, model) from err

    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as err:
        log.error("неожиданная форма ответа Яндекса: %s", str(body)[:500])
        raise AiUnavailable("Модель вернула ответ неожиданной формы.") from err
    return _parse_card(text)


def _yandex_post(payload: dict, allow_retry: bool) -> dict | None:
    """Один запрос к Яндексу. None означает «схему не приняли, попробуй без неё»."""
    import httpx

    try:
        response = httpx.post(
            YANDEX_URL,
            json=payload,
            headers={"Authorization": f"Api-Key {yandex_key()}"},
            timeout=90.0,
        )
    except Exception as err:
        log.exception("запрос к Яндексу не удался")
        raise AiUnavailable(
            f"Не удалось связаться с Яндексом. {type(err).__name__}: {err}"[:300]
        ) from err

    if allow_retry and response.status_code == 400:
        log.warning("Яндекс не принял response_format, повторяю без схемы")
        return None
    if response.status_code >= 400:
        # Текст ошибки показываем как есть: без него «403» ничего не объясняет,
        # а чинится оно по-разному — не тот каталог, не выданная роль, не
        # открытая модель. Ключ передаётся в заголовке запроса и в ответ
        # не попадает, так что показывать тело безопасно.
        log.error("Яндекс ответил %s: %s", response.status_code, response.text[:1000])
        raise AiUnavailable(
            f"Яндекс ответил {response.status_code}. {_yandex_error_text(response)}"[:300]
        )
    try:
        return response.json()
    except ValueError as err:
        log.error("Яндекс вернул не JSON: %s", response.text[:500])
        raise AiUnavailable("Яндекс вернул ответ неожиданной формы.") from err


def _yandex_error_text(response) -> str:
    """Вытащить человеческое объяснение из ответа об ошибке."""
    try:
        body = response.json()
    except ValueError:
        return response.text.strip()[:200]
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)[:200]
        if error:
            return str(error)[:200]
        if body.get("message"):
            return str(body["message"])[:200]
    return str(body)[:200]


def _explain_refusal(err: AiUnavailable, model: str) -> AiUnavailable:
    """Дополнить отказ списком моделей, открытых каталогу.

    «403 Forbidden» без тела не отличает «каталогу не открыта эта модель» от
    «ключу не выдана роль». Список моделей отвечает на это сразу: если нужной
    в нём нет — дело в модели, если есть — в правах.
    """
    text = str(err)
    if " 403" not in text and " 404" not in text:
        return err
    available = _yandex_models()
    if not available:
        return err
    return AiUnavailable(
        f"{text} Модель {model}: "
        + ("доступна каталогу, дело в правах ключа." if model in available
           else "каталогу не открыта. Открытые: " + ", ".join(available[:15]))
    )


def _yandex_models() -> list[str]:
    """Короткие имена моделей, доступных каталогу. Пустой список — не удалось узнать."""
    import httpx

    try:
        response = httpx.get(
            YANDEX_MODELS_URL,
            headers={
                "Authorization": f"Api-Key {yandex_key()}",
                # Так каталог передаёт их собственный SDK: не в URI, а заголовком.
                "OpenAI-Project": yandex_folder() or "",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
    except Exception:
        log.exception("не удалось получить список моделей Яндекса")
        return []
    # id приходит целым URI gpt://<каталог>/<модель>/<версия> — оставляем модель:
    # каталог в сообщении на странице ни к чему.
    names = []
    for item in data:
        parts = str(item.get("id", "")).split("/")
        if len(parts) >= 4:
            names.append(parts[3])
    return names


def _parse_card(text: str) -> dict:
    """Разобрать ответ модели.

    Терпим к обёрткам: модель может завернуть JSON в ```-блок или добавить
    строку до него. Берём от первой { до последней } — на карточке это
    надёжнее, чем требовать идеально чистый ответ.
    """
    chunk = text.strip()
    start, end = chunk.find("{"), chunk.rfind("}")
    if start != -1 and end > start:
        chunk = chunk[start : end + 1]
    try:
        card = json.loads(chunk)
    except json.JSONDecodeError as err:
        log.error("неразборчивый ответ модели: %s", text[:500])
        raise AiUnavailable("Модель вернула неразборчивый ответ.") from err

    # Приводим к ожидаемому виду: не все модели держат схему дословно.
    card.setdefault("recognized", bool(card.get("name")))
    for field in CARD_SCHEMA["required"]:
        card.setdefault(field, "")
    return normalise_card(card)


# Как модели называют классы виски на самом деле. Ключ — то, что встречается
# в ответе, значение — наш словарь из models.WHISKY_CLASSES. Класс важен не
# косметически: по нему начисляются частичные баллы (docs/SCORING.md).
_CLASS_ALIASES = {
    "single malt": "односолодовый скотч",
    "односолодовый": "односолодовый скотч",
    "односолодовый виски": "односолодовый скотч",
    "solod": "односолодовый скотч",
    "blended": "купажированный скотч",
    "blend": "купажированный скотч",
    "купаж": "купажированный скотч",
    "купажированный": "купажированный скотч",
    "bourbon": "бурбон",
    "rye": "ржаной",
    "ржаной виски": "ржаной",
}


def normalise_card(card: dict) -> dict:
    """Причесать ответ модели до вида, пригодного для справочника.

    Модель охотно пишет «40%», «10 лет», «около 8000 ₽» и «Single Malt».
    Пока это только текст на карточке — неважно; но админ сохраняет карточку
    в справочник, где крепость обязана быть числом, а класс — одним из наших,
    иначе частичные баллы посчитаются неверно.
    """
    for field in ("abv", "age_years", "price_rub"):
        card[field] = _only_number(card.get(field))

    wclass = (card.get("wclass") or "").strip()
    lowered = wclass.casefold()
    for alias, ours in _CLASS_ALIASES.items():
        if alias in lowered:
            card["wclass"] = ours
            break

    confidence = (card.get("confidence") or "").strip().casefold()
    card["confidence"] = confidence if confidence in {"высокая", "средняя", "низкая"} else ""

    # recognized обязано стать настоящим bool. Модель охотно присылает строку
    # "false", а непустая строка в шаблоне истинна — страница уходила в ветку
    # «узнал» с пустым названием вместо честного «не узнал».
    card["recognized"] = _as_bool(card.get("recognized")) and bool(str(card.get("name") or "").strip())
    return card


_FALSE_WORDS = {"", "false", "no", "нет", "0", "none", "null"}


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() not in _FALSE_WORDS
    return bool(value)


def _only_number(value) -> str:
    """Оставить от «около 41,5 %» одно число. Пусто, если чисел нет вовсе."""
    if value is None:
        return ""
    match = re.search(r"\d+(?:[.,]\d+)?", str(value))
    return match.group(0).replace(",", ".") if match else ""


# ── кэш ────────────────────────────────────────────────────────────────────


def _from_cache(key: str) -> dict | None:
    """Достать карточку из кэша.

    Причёсываем на чтении, а не только при записи: в кэше осели ответы,
    полученные до появления normalise_card, и показывать «40% %» из-за них
    неправильно. Заодно причёсывание работает для всех путей сразу.
    """
    with connect() as conn:
        row = conn.execute("SELECT payload FROM ai_cache WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return normalise_card(json.loads(row["payload"]))


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
