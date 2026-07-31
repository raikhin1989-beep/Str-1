"""Вход в админку: сессионная кука и защита от перебора пароля."""

import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.config import admin_password, session_ttl_days
from app.db import connect, log_action

COOKIE_NAME = "str1_admin"

# Защита от перебора: после стольких неудач с одного адреса вход запирается
# на LOCKOUT_SECONDS. Счётчик в памяти процесса — приложение одно, этого хватает,
# а перезапуск службы сбрасывает блокировку, что для нас приемлемо.
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300
_failures: dict[str, list[float]] = {}


def client_ip(request: Request) -> str:
    """Адрес посетителя.

    В приложение ходит только Caddy с localhost, поэтому X-Forwarded-For здесь
    можно доверять: подделать его снаружи, минуя прокси, нельзя.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "?"


def is_locked_out(ip: str) -> int:
    """Сколько секунд осталось до конца блокировки; 0 — не заблокирован."""
    attempts = [t for t in _failures.get(ip, []) if time.time() - t < LOCKOUT_SECONDS]
    _failures[ip] = attempts
    if len(attempts) < MAX_ATTEMPTS:
        return 0
    return int(LOCKOUT_SECONDS - (time.time() - attempts[0])) + 1


def note_failure(ip: str) -> None:
    _failures.setdefault(ip, []).append(time.time())


def reset_failures(ip: str) -> None:
    _failures.pop(ip, None)


def password_matches(candidate: str) -> bool:
    expected = admin_password()
    if not expected:
        return False
    # compare_digest вместо == : сравнение за постоянное время.
    # Сравниваем байты, а не строки: со строками compare_digest не принимает
    # ничего вне ASCII и падает на кириллическом пароле.
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def start_session(ip: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=session_ttl_days())
    with connect() as conn:
        conn.execute(
            "INSERT INTO admin_session (token, expires_at, ip) VALUES (?, ?, ?)",
            (token, expires.isoformat(), ip),
        )
        _drop_expired(conn)
        log_action(conn, ip, "admin.login", "вход в админку")
    return token


def end_session(token: str, ip: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM admin_session WHERE token = ?", (token,))
        log_action(conn, ip, "admin.logout", "выход из админки")


def session_is_valid(token: str | None) -> bool:
    if not token:
        return False
    with connect() as conn:
        _drop_expired(conn)
        row = conn.execute(
            "SELECT 1 FROM admin_session WHERE token = ? AND expires_at > ?",
            (token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    return row is not None


def _drop_expired(conn) -> None:
    conn.execute(
        "DELETE FROM admin_session WHERE expires_at <= ?",
        (datetime.now(timezone.utc).isoformat(),),
    )


def is_secure_request(request: Request) -> bool:
    """Пришёл ли запрос по HTTPS.

    Нужно для флага Secure у куки: домен работает по HTTPS, а запасной вход на
    порту 8081 — по HTTP, и там кука с Secure просто не сохранилась бы.
    """
    proto = request.headers.get("x-forwarded-proto", "")
    return proto == "https" or request.url.scheme == "https"
