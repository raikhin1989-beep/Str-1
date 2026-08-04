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
import threading
import time

from app.config import ai_provider, anthropic_key, photo_lookup, yandex_folder, yandex_key
from app.db import connect

log = logging.getLogger("str1.ai")

ANTHROPIC_MODEL = "claude-opus-5"

# Yandex AI Studio, OpenAI-совместимый эндпоинт — тот же, которым пользуется
# их официальный SDK (yandex-cloud/yandex-ai-studio-sdk).
YANDEX_URL = "https://llm.api.cloud.yandex.net/v1/chat/completions"
# Список моделей, доступных каталогу. Спрашиваем только когда в доступе отказали:
# по нему сразу видно, открыта ли каталогу нужная модель вообще.
YANDEX_MODELS_URL = "https://llm.api.cloud.yandex.net/v1/models"

# Yandex Vision OCR: читает текст с картинки. Для этикетки это надёжнее любой
# языковой модели — название, крепость и выдержка на ней просто написаны.
# Адрес и форма запроса взяты из их же protobuf (yandex/cloud/ai/ocr/v1).
YANDEX_OCR_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"
OCR_MIME = {"image/jpeg": "JPEG", "image/png": "PNG"}
OCR_MAX_CHARS = 1500
YANDEX_TEXT_MODEL = "yandexgpt"
# Кандидаты на разбор фотографии, в порядке предпочтения. Первым идёт
# gemma-3-27b-it: в примере multimodal.py их SDK сказано, что картинки
# понимает только она. Нашему каталогу её не выдали, поэтому дальше идут
# остальные модели, у которых есть шанс, — берётся первая доступная.
YANDEX_VISION_MODELS = (
    "gemma-3-27b-it",
    "aliceai-vlm",
    "aliceai-llm",
    "aliceai-llm-flash",
)

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
            "description": (
                "односолодовый скотч, купажированный скотч, "
                "односолодовый (не Шотландия), ирландский, японский, "
                "бурбон, теннесси, ржаной или прочее"
            ),
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
    """Предлагать ли гостю загрузить фотографию.

    Код для фото готов у обоих провайдеров, а вот работает он не везде, и
    зависит это от прав в чужой консоли, а не от нашего кода. Поэтому кнопку
    показываем не по догадке, а по факту: у Яндекса спрашиваем сам Vision OCR,
    отвечает ли он нам (ocr_allowed). У Anthropic картинку понимает сама
    модель — там спрашивать нечего.

    Ручное переопределение AI_PHOTO сильнее любой проверки: `off` прячет
    кнопку и там, где всё работает, `on` показывает вопреки отказу — иногда
    надо увидеть настоящую ошибку, а не спрятанную кнопку.
    """
    current = ai_provider()
    if current is None:
        return False
    override = photo_lookup()
    if override is not None:
        return override
    if current == "anthropic":
        return True
    return ocr_allowed()


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

    Тот же адрес и та же форма запроса, что у их официального SDK. Текст
    обслуживает yandexgpt; для фотографии модель подбирается из тех, что
    открыты каталогу — набор моделей у каждого каталога свой.
    """
    if image is None:
        return _yandex_card(YANDEX_TEXT_MODEL, prompt, None)

    problems = []

    # Сначала читаем этикетку OCR: название, крепость и выдержка на ней
    # написаны буквами, и языковой модели остаётся только опознать розлив.
    try:
        label = _yandex_ocr(image)
    except AiUnavailable as err:
        label = ""
        log.warning("OCR не сработал: %s", err)
        problems.append(f"чтение этикетки — {err}")
    if label:
        card = _yandex_card(YANDEX_TEXT_MODEL, _prompt_with_label(prompt, label), None)
        card["via"] = "текст с этикетки прочитан Yandex Vision OCR"
        return card

    # Этикетку прочитать не вышло — показываем саму фотографию той модели,
    # которая на это способна.
    try:
        candidates = _vision_candidates()
    except AiUnavailable as err:
        # Не теряем причину, по которой не сработало чтение этикетки: чинить,
        # скорее всего, надо именно её, а не набор моделей.
        problems.append(str(err))
        candidates = []
    for model in candidates:
        try:
            card = _yandex_card(model, prompt, image)
        except AiUnavailable as err:
            log.warning("модель %s не разобрала фото: %s", model, err)
            problems.append(f"{model} — {err}")
            continue
        if _did_not_see_the_image(card):
            # Текстовая модель принимает запрос с картинкой, но саму картинку
            # не видит и честно пишет «фото не приложено». Такой ответ хуже
            # отказа: выглядит как результат. Идём к следующей модели.
            log.warning("модель %s картинку не увидела", model)
            problems.append(f"{model} — картинку не увидела")
            continue
        log.info("фото разобрала модель %s", model)
        # Что не сработало до этого — тоже пишем: карточка от модели, которая
        # фотографию не увидела, выглядит как обычный отказ, и без этой строки
        # непонятно, чинить чтение этикетки или ответ модели.
        card["via"] = f"фотографию смотрела модель {model}"
        if problems:
            card["via"] += ". До этого не вышло: " + "; ".join(problems)
        return card
    raise AiUnavailable(_photo_failure(problems))


# Как выглядит ответ модели, до которой картинка не доехала.
_BLIND_ANSWER = ("фото не", "фотография не", "изображение не", "картинк", "не прикреплен", "не предоставлен")


def _did_not_see_the_image(card: dict) -> bool:
    if card.get("recognized"):
        return False
    comment = (card.get("comment") or "").casefold()
    return any(mark in comment for mark in _BLIND_ANSWER)


def _photo_failure(problems: list[str]) -> str:
    """Собрать отказ так, чтобы из него было понятно, что чинить."""
    parts = ["Распознать фотографию не удалось."]
    # 403 у OCR — это не поломка, а недоданное право: чинится одной ролью
    # в консоли Yandex Cloud, поэтому говорим об этом прямо.
    if any("403" in problem for problem in problems if problem.startswith("чтение этикетки")):
        parts.append(
            "Чтение этикетки (Yandex Vision OCR) отвечает «нет доступа». "
            "Причин ровно две, и нужны обе: сервисному аккаунту — роль "
            "ai.vision.user на каталог, API-ключу — область действия "
            "yc.ai.vision.execute. Область задаётся при создании ключа и "
            "не меняется: если она другая, ключ выпускается заново."
        )
    parts.append("Подробности: " + "; ".join(problems) + ".")
    return " ".join(parts)[:700]


def _prompt_with_label(prompt: str, label: str) -> str:
    return (
        prompt
        + "\n\nСамой фотографии у тебя нет — вот текст, распознанный на этикетке "
        "(строки идут как на бутылке, возможны ошибки распознавания):\n"
        f"«{label}»\n"
        "Опознай виски по этому тексту. Если текста слишком мало или он не про "
        "виски, ставь recognized=false и скажи в comment, что именно прочиталось."
    )


def _yandex_ocr(image: tuple[bytes, str]) -> str:
    """Текст с этикетки. Пустая строка означает «прочитать нечего»."""
    import base64

    import httpx

    image_bytes, media_type = image
    mime = OCR_MIME.get(media_type)
    if mime is None:
        # WebP этот сервис не принимает — не ошибка, просто идём дальше.
        return ""

    try:
        response = httpx.post(
            YANDEX_OCR_URL,
            json={
                "content": base64.standard_b64encode(image_bytes).decode("ascii"),
                "mimeType": mime,
                "languageCodes": ["*"],
                "model": "page",
            },
            headers={
                "Authorization": f"Api-Key {yandex_key()}",
                "x-folder-id": yandex_folder() or "",
            },
            timeout=60.0,
        )
    except Exception as err:
        log.exception("запрос к Vision OCR не удался")
        raise AiUnavailable(f"{type(err).__name__}: {err}"[:200]) from err

    if response.status_code >= 400:
        log.error("Vision OCR ответил %s: %s", response.status_code, response.text[:500])
        raise AiUnavailable(f"{response.status_code}. {_yandex_error_text(response)}"[:200])

    try:
        body = response.json()
    except ValueError as err:
        raise AiUnavailable("ответ неожиданной формы") from err
    # Метод потоковый, поэтому REST заворачивает страницу в result.
    page = body.get("result", body)
    text = (page.get("textAnnotation") or {}).get("fullText") or ""
    return " ".join(text.split())[:OCR_MAX_CHARS]


def _vision_candidates() -> list[str]:
    """Модели, которым имеет смысл показать фотографию, в порядке предпочтения.

    Пересекаем свой список с тем, что открыто каталогу: жёстко зашитое имя
    ломается молча, когда каталогу его не выдали, — так уже случилось
    с gemma-3-27b-it.
    """
    available = _yandex_models()
    if not available:
        # Список получить не удалось — пробуем всё, что знаем: отказ по каждой
        # модели всё равно попадёт в сообщение.
        return list(YANDEX_VISION_MODELS)
    candidates = [name for name in YANDEX_VISION_MODELS if name in available]
    if candidates:
        return candidates
    raise AiUnavailable(
        "В каталоге Yandex Cloud не открыта ни одна модель, понимающая "
        "изображения. Открыты: " + ", ".join(available[:20])
    )


def _yandex_card(model: str, prompt: str, image: tuple[bytes, str] | None) -> dict:
    """Один заход к конкретной модели Яндекса."""
    import base64

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

    # 400 — «схему не приняли», 500 — так отвечают некоторые модели на тот же
    # response_format. В обоих случаях есть смысл повторить без схемы.
    if allow_retry and response.status_code in {400, 500}:
        log.warning("Яндекс ответил %s на запрос со схемой, повторяю без неё", response.status_code)
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


# Список моделей меняется редко, а спрашивают его по нескольку раз за один
# неудачный запрос — держим ответ в памяти процесса на четверть часа.
_models_cache: tuple[float, list[str]] | None = None
MODELS_CACHE_SECONDS = 900


def _yandex_models() -> list[str]:
    """Короткие имена моделей, доступных каталогу. Пустой список — не удалось узнать."""
    global _models_cache

    import httpx

    if _models_cache is not None and time.time() - _models_cache[0] < MODELS_CACHE_SECONDS:
        return _models_cache[1]
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
    _models_cache = (time.time(), names)
    return names


def reset_models_cache() -> None:
    """Забыть список моделей — нужно тестам и после смены ключа."""
    global _models_cache

    _models_cache = None


# ── доступен ли нам Vision OCR ──────────────────────────────────────────────
#
# Права на чтение этикетки живут в чужой консоли и меняются без нашего ведома:
# роль выдали — заработало, ключ перевыпустили с другой областью — отвалилось.
# Раньше это отражал секрет AI_PHOTO, который ставили руками и проверяли
# выкатом. Теперь спрашиваем у самого OCR.
#
# Настоящая картинка 1×1, а не мусор: на битом теле сервис может ответить 400
# ещё до проверки ключа, и тогда «400» означало бы не «нам можно», а «мы даже
# не дошли до авторизации». На корректном запросе ответ однозначен.
OCR_PROBE_JPEG = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)
# Разрешение держим дольше отказа: отказ хочется перепроверять часто — роль
# выдали в консоли, и кнопка должна появиться сама, без выката.
OCR_PROBE_OK_SECONDS = 3600
OCR_PROBE_FAIL_SECONDS = 300

_ocr_cache: tuple[float, bool] | None = None
_ocr_lock = threading.Lock()
_ocr_probing = False


def ocr_allowed() -> bool:
    """Отвечает ли нам Vision OCR. Не ходит в сеть на этом вызове.

    Вызывается при отрисовке страницы поиска, поэтому обязана быть мгновенной:
    /api/health уже однажды повис на двадцать секунд из-за похожего вопроса,
    заданного по дороге. Ответ берётся из памяти, а обновляется фоном.

    Пока ответа нет, кнопки нет: обещать гостю распознавание, о котором мы
    ничего не знаем, хуже, чем не показать её первые пару секунд после
    перезапуска.
    """
    if yandex_key() is None:
        return False
    cached = _ocr_cache
    if cached is not None:
        age = time.time() - cached[0]
        if age < (OCR_PROBE_OK_SECONDS if cached[1] else OCR_PROBE_FAIL_SECONDS):
            return cached[1]
    _probe_ocr_in_background()
    return cached[1] if cached is not None else False


def _probe_ocr_in_background() -> None:
    """Обновить ответ, не задерживая текущий запрос."""
    global _ocr_probing

    with _ocr_lock:
        if _ocr_probing:
            return
        _ocr_probing = True
    threading.Thread(target=_probe_ocr, name="ocr-probe", daemon=True).start()


def _probe_ocr() -> None:
    global _ocr_cache, _ocr_probing

    try:
        _ocr_cache = (time.time(), _ask_ocr_whether_we_may())
    finally:
        with _ocr_lock:
            _ocr_probing = False


def _ask_ocr_whether_we_may() -> bool:
    import httpx

    try:
        response = httpx.post(
            YANDEX_OCR_URL,
            json={
                "content": OCR_PROBE_JPEG,
                "mimeType": "JPEG",
                "languageCodes": ["*"],
                "model": "page",
            },
            headers={
                "Authorization": f"Api-Key {yandex_key()}",
                "x-folder-id": yandex_folder() or "",
            },
            timeout=10.0,
        )
    except Exception as err:
        # Сеть, а не права. Считаем, что нельзя: короткий срок отказа
        # заставит спросить снова через пять минут.
        log.warning("Vision OCR не ответил на проверку прав: %s", err)
        return False

    if response.status_code in (401, 403):
        log.warning(
            "Vision OCR закрыт (%s): нужны роль ai.vision.user у сервисного "
            "аккаунта и область yc.ai.vision.execute у ключа",
            response.status_code,
        )
        return False
    if response.status_code >= 500:
        log.warning("Vision OCR отвечает %s — считаем недоступным", response.status_code)
        return False
    # 200 — прочитал (на картинке 1×1 читать нечего, и это нормально).
    # 4xx кроме отказов — запрос не понравился, но до нас дошли и пустили.
    log.info("Vision OCR доступен (ответ %s)", response.status_code)
    return True


def reset_ocr_cache() -> None:
    """Забыть, отвечает ли OCR. Нужно тестам и после смены ключа."""
    global _ocr_cache

    _ocr_cache = None


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
    "irish": "ирландский",
    "ирландский виски": "ирландский",
    "japanese": "японский",
    "японский виски": "японский",
    "bourbon": "бурбон",
    "tennessee": "теннесси",
    "теннесси": "теннесси",
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
    """Запомнить карточку. Неудачу не запоминаем.

    Кэш вечный, и «не узнал» в нём — ловушка. Однажды так и вышло: фотографию
    Laphroaig принесли, когда у нас не было прав на чтение этикетки, ответ
    «фотография не приложена» осел в кэше — и после починки прав та же самая
    фотография продолжала получать старый отказ, мгновенно и мимо модели.

    Неудача почти всегда про обстоятельства — права, сеть, занятая модель, —
    а не про саму картинку, и повторить попытку должно быть можно. Стоимость
    повтора ограничивает не кэш, а счётчик запросов с адреса.
    """
    if not card.get("recognized"):
        return
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
