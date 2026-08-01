"""Ограничение частоты запросов на публичных формах.

Счётчик в памяти процесса: приложение одно, переживать перезапуск ему незачем,
а лишняя таблица в базе на каждый клик — плохая цена за защиту от шалости.

Ограничение здесь не про взлом, а про то, чтобы шутник с телефона не завёл
двести участников за минуту и не сорвал вечер.
"""

import time

# Сколько действий с одного адреса за окно.
LIMITS = {
    "join": (10, 600),      # регистраций за 10 минут
    "draft": (240, 600),    # автосохранений черновика: раз в 2-3 секунды это норма
}

_seen: dict[tuple[str, str], list[float]] = {}


class TooOften(Exception):
    """Слишком часто с одного адреса."""


def check(kind: str, ip: str) -> None:
    limit, window = LIMITS[kind]
    now = time.time()
    key = (kind, ip)
    recent = [moment for moment in _seen.get(key, []) if now - moment < window]
    _seen[key] = recent
    if len(recent) >= limit:
        raise TooOften
    recent.append(now)


def reset() -> None:
    """Забыть счётчики — нужно тестам."""
    _seen.clear()
