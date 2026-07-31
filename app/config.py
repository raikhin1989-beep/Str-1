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


def photo_lookup() -> bool:
    """Показывать ли загрузку фотографии.

    У Яндекса фото упирается не в код, а в права: чтение этикетки (Vision OCR)
    отвечает 403, пока сервисному аккаунту не выдана роль ai.vision.user, а
    моделей, понимающих картинку, каталогу не открыто (docs/PLAN.md, шаг 4).
    Пока прав нет, кнопка только обманывает гостя, поэтому по умолчанию она
    спрятана; AI_PHOTO=on включает её обратно без правки кода.

    У Anthropic картинку понимает сама модель — там включено сразу.
    """
    switch = os.environ.get("AI_PHOTO", "").strip().lower()
    if switch in {"on", "1", "yes", "да"}:
        return True
    if switch in {"off", "0", "no", "нет"}:
        return False
    return ai_provider() == "anthropic"
