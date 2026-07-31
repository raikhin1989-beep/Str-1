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
