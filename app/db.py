"""Подключение к SQLite и накатывание миграций.

Миграции — нумерованные .sql в app/migrations, применяются по порядку и
запоминаются в schema_migrations. Откат — восстановлением из бэкапа, см.
docs/OPERATIONS.md.
"""

import sqlite3
import threading
from pathlib import Path

from app.config import db_path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Схему накатываем один раз на путь к базе. Блокировка нужна, потому что
# uvicorn обслуживает запросы в нескольких потоках.
_ready: set[str] = set()
_lock = threading.Lock()


class _Connection(sqlite3.Connection):
    """Соединение, которое закрывается вместе с блоком `with`.

    Штатный `with sqlite3.connect(...)` — ловушка, и она нас уже подвела.
    Он фиксирует транзакцию, но соединение оставляет открытым: закрыть его
    должен сборщик мусора, когда до переменной дойдут руки. Пока запросов
    мало, это незаметно; когда за столом несколько телефонов опрашивают
    сервер раз в три секунды, дескрипторы копятся быстрее, чем убираются.

    Чем это кончилось 5 августа: у процесса кончились файловые дескрипторы,
    и приложение перестало открывать что бы то ни было — базу, сокет
    к Yandex OCR, даже шаблон страницы ошибки. Снаружи это выглядело как
    «отказала база»: `unable to open database file`, а следом голое
    «Internal Server Error» вместо оформленной страницы, потому что и её
    файл прочитать было нечем.

    Поэтому закрываем сами. Так все 39 мест вида `with connect() as conn:`
    остаются как есть и при этом перестают течь.
    """

    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def connect() -> sqlite3.Connection:
    """Соединение с готовой схемой.

    Закрывается само при выходе из `with`. Если берёте его без `with` —
    закрывайте руками, как это делает app/backup.py.
    """
    path = db_path()
    _ensure_schema(path)
    return _open(path)


def _open(path: Path, autoclose: bool = True) -> sqlite3.Connection:
    # autoclose=False — для накатывания миграций: там одно соединение живёт
    # через несколько `with` подряд (по одному на миграцию), и закрываться
    # после первой же оно не должно. Жизненным циклом там управляют руками.
    conn = sqlite3.connect(path, timeout=10, factory=_Connection if autoclose else sqlite3.Connection)
    conn.row_factory = sqlite3.Row
    # WAL — чтобы чтение не блокировалось записью; foreign_keys в SQLite
    # выключены по умолчанию и включаются на каждое соединение отдельно.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema(path: Path) -> None:
    key = str(path)
    if key in _ready:
        return
    with _lock:
        if key in _ready:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = _open(path, autoclose=False)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " name TEXT PRIMARY KEY,"
                " applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            applied = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
            for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if sql_file.name in applied:
                    continue
                with conn:
                    conn.executescript(sql_file.read_text(encoding="utf-8"))
                    conn.execute(
                        "INSERT INTO schema_migrations (name) VALUES (?)", (sql_file.name,)
                    )
        finally:
            conn.close()
        _ready.add(key)


def reset_schema_cache() -> None:
    """Забыть, что схема накатана. Нужно тестам, которые меняют путь к базе."""
    with _lock:
        _ready.clear()


def log_action(conn: sqlite3.Connection, ip: str | None, action: str, details: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (ip, action, details) VALUES (?, ?, ?)",
        (ip, action, details),
    )
