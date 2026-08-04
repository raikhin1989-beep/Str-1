"""Настройки из окружения.

Значения читаются при каждом обращении, а не один раз при импорте: так тесты
могут подменить окружение, а служба — перечитать секрет после перезапуска.
Значения секретов никуда не логируются.
"""

import os
from pathlib import Path

# База лежит вне докрута намеренно: /var/www/str-1 синхронизируется с --delete
# и всё лишнее там стирается следующим деплоем. См. docs/ARCHITECTURE.md.
DEFAULT_DB_PATH = "/var/lib/str-1/app.db"


def db_path() -> Path:
    return Path(os.environ.get("STR1_DB_PATH", DEFAULT_DB_PATH))


def admin_password() -> str:
    """Пароль админки. Пустая строка означает «админка выключена»."""
    return os.environ.get("ADMIN_PASSWORD", "")


def session_ttl_days() -> int:
    return int(os.environ.get("STR1_SESSION_TTL_DAYS", "14"))


def public_base_url() -> str:
    """Адрес, по которому сайт открывают гости.

    Нужен для ссылок и QR-кодов. Без него они собираются из адреса, по которому
    сейчас открыта админка, — а её открывают и по запасному входу
    `http://<адрес>:8081/`, и тогда гостю уезжает ссылка на порт 8081 вместо
    домена. Задаётся деплоем из SITE_DOMAIN.
    """
    return os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")


def anthropic_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "")


def yandex_key() -> str:
    return os.environ.get("YANDEX_API_KEY", "")


def yandex_folder() -> str:
    return os.environ.get("YANDEX_FOLDER_ID", "")


def ai_provider() -> str | None:
    """Кто отвечает за распознавание виски.

    Выбор — по тому, до чего может дотянуться СЕРВЕР, а не по стране гостя:
    запрос к модели уходит с сервера, и для Anthropic важно, где стоит он.
    Наш сервер в Москве, откуда Anthropic API не обслуживается, поэтому при
    наличии ключей Яндекса он и выбирается. Переменная AI_PROVIDER позволяет
    задать провайдера явно — например, после переезда на другой хостинг.
    """
    forced = os.environ.get("AI_PROVIDER", "").strip().lower()
    if forced in {"yandex", "anthropic"}:
        return forced
    if forced == "off":
        return None
    if yandex_key() and yandex_folder():
        return "yandex"
    if anthropic_key():
        return "anthropic"
    return None


def photo_lookup() -> bool | None:
    """Показывать ли загрузку фотографии: да, нет или «решай сам».

    Настройка `AI_PHOTO` — только ручное переопределение, и None означает, что
    его не задали. Кто решает по умолчанию — `ai.supports_images()`.

    Почему настройка вообще есть. У Яндекса фото упирается не в код, а в права:
    чтение этикетки (Vision OCR) отвечает 403, пока не сделаны обе разные вещи —
    сервисному аккаунту не выдана роль ai.vision.user на каталог, а API-ключу
    не задана область действия yc.ai.vision.execute. Роль даёт право аккаунту,
    область разрешает ключу этим правом пользоваться. Обходного пути нет:
    моделей, понимающих картинку, каталогу не открыто (docs/PLAN.md, шаг 4).

    Раньше здесь стояло «у Яндекса спрятано, пока не скажут иначе», и права
    приходилось угадывать руками: выставить секрет, выкатить, посмотреть.
    Теперь про них спрашивают у самого OCR, а настройка осталась на случай,
    когда решение нужно продавить: `on` — показать несмотря ни на что,
    `off` — спрятать даже там, где работает.
    """
    switch = os.environ.get("AI_PHOTO", "").strip().lower()
    if switch in {"on", "1", "yes", "да"}:
        return True
    if switch in {"off", "0", "no", "нет"}:
        return False
    return None
