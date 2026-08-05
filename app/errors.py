"""Последние сбои приложения — так, чтобы их было видно без SSH.

Полная трасса и раньше уходила в журнал службы, но добраться до неё можно
только с ноутбука и по SSH. Ровно тогда, когда она нужна, — посреди вечера,
с телефона в руке, — это недоступно. Первый же живой тест это и показал:
«Internal Server Error» был, а что именно упало, узнать было неоткуда.

Поэтому короткая выжимка складывается ещё и в базу: тип ошибки, адрес
страницы и то место в нашем коде, где всё случилось. Достаточно, чтобы
понять, что чинить, и мало, чтобы утащить в лог чужие данные.

Живёт в audit_log с действием error.<тип>: отдельная таблица ради этого
не нужна, а ротация уже есть — база целиком уезжает в бэкап.
"""

import traceback

from app.db import connect

# Сколько кадров трассы оставляем. Нужен верхний — тот, где ошибка возникла,
# и пара под ним, чтобы понять, кто позвал.
FRAMES = 4
DETAILS_LIMIT = 900


def remember(path: str, exc: BaseException) -> None:
    """Записать сбой. Сама эта запись упасть не имеет права.

    Обработчик ошибок — последнее место, где можно ронять приложение: гость
    вместо понятной страницы получил бы пустой ответ от сервера.
    """
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO audit_log (ip, action, details) VALUES (?, ?, ?)",
                (None, f"error.{type(exc).__name__}", _details(path, exc)),
            )
    except Exception:  # noqa: BLE001 — тут действительно всё равно, что упало
        pass


def _details(path: str, exc: BaseException) -> str:
    where = []
    for frame in traceback.extract_tb(exc.__traceback__)[-FRAMES:]:
        # Только имя файла: полный путь на сервере длинный и ничего не добавляет.
        name = frame.filename.rsplit("/", 1)[-1]
        where.append(f"{name}:{frame.lineno} {frame.name}")
    return f"{path} · {exc} · {' ← '.join(reversed(where)) or 'место неизвестно'}"[:DETAILS_LIMIT]


def recent(limit: int = 30) -> list:
    """Последние сбои, свежие сверху."""
    with connect() as conn:
        return conn.execute(
            "SELECT at, action, details FROM audit_log"
            " WHERE action LIKE 'error.%' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()


def forget() -> None:
    """Убрать разобранные сбои, чтобы список не мозолил глаза."""
    with connect() as conn:
        conn.execute("DELETE FROM audit_log WHERE action LIKE 'error.%'")
