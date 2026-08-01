"""Телеграм-бот: привязка участников и отправка сообщений.

Почему привязка вообще нужна: Bot API умеет писать только тому, кто сам начал
диалог с ботом, и адресуется не по @username, а по chat_id. Поэтому участник
жмёт кнопку со ссылкой t.me/<бот>?start=<токен>, бот получает этот токен
и связывает chat_id с записью участника.
"""

import logging
import os
import time

import httpx

log = logging.getLogger("str1.telegram")

API = "https://api.telegram.org"
TIMEOUT = 5.0

# Имя бота нужно для deep link'а. Основной путь — переменная окружения:
# её заполняет деплой, спросив у API с раннера GitHub. С самого сервера
# api.telegram.org может быть недоступен (проверено: TCP-таймаут), и тогда
# запрос отсюда — это только потерянные секунды на каждой странице.
#
# Запоминаем и неудачу тоже: без этого каждая страница гостя ждала бы
# ответа от недоступного API, и /me открывалась бы по пять секунд.
_username: str | None = None
_asked_at: float = 0.0
ASK_AGAIN_AFTER = 600.0


def token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def webhook_secret() -> str:
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")


def is_configured() -> bool:
    return bool(token() and webhook_secret())


def bot_username() -> str | None:
    """@имя бота без собачки. None, если узнать не удалось."""
    global _username, _asked_at

    forced = os.environ.get("TELEGRAM_BOT_USERNAME", "").lstrip("@")
    if forced:
        return forced
    if _username:
        return _username
    if not token():
        return None
    if time.time() - _asked_at < ASK_AGAIN_AFTER:
        # Недавно спрашивали и не получилось — не заставляем гостя ждать снова.
        return None

    _asked_at = time.time()
    try:
        response = httpx.get(f"{API}/bot{token()}/getMe", timeout=TIMEOUT)
        response.raise_for_status()
        _username = response.json()["result"]["username"]
    except Exception as err:
        log.warning("не удалось узнать имя бота: %s", err)
        return None
    return _username


def known_username() -> str | None:
    """Имя бота, если оно уже известно. В сеть не ходит никогда."""
    return os.environ.get("TELEGRAM_BOT_USERNAME", "").lstrip("@") or _username


def forget_username() -> None:
    """Забыть, что имя спрашивали. Нужно тестам."""
    global _username, _asked_at

    _username = None
    _asked_at = 0.0


def deep_link(join_token: str) -> str | None:
    name = bot_username()
    return f"https://t.me/{name}?start={join_token}" if name else None


def send_message(chat_id: int, text: str) -> bool:
    """Отправить сообщение. Возвращает, дошло ли — рассылка не должна падать."""
    if not token():
        return False
    try:
        response = httpx.post(
            f"{API}/bot{token()}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return True
    except Exception:
        log.exception("не удалось отправить сообщение в чат %s", chat_id)
        return False


def set_webhook(url: str) -> tuple[bool, str]:
    """Прописать адрес вебхука. Вызывается деплоем, а не приложением."""
    if not is_configured():
        return False, "нет TELEGRAM_BOT_TOKEN или TELEGRAM_WEBHOOK_SECRET"
    try:
        response = httpx.post(
            f"{API}/bot{token()}/setWebhook",
            json={
                "url": url,
                "secret_token": webhook_secret(),
                # Нас интересуют только сообщения: на всё остальное бот
                # не реагирует, и получать это лишний раз незачем.
                "allowed_updates": ["message"],
                "drop_pending_updates": True,
            },
            timeout=TIMEOUT,
        )
        body = response.json()
    except Exception as err:
        return False, f"{type(err).__name__}: {err}"
    return bool(body.get("ok")), str(body.get("description", ""))


def parse_start_command(update: dict) -> tuple[int, str, str | None] | None:
    """Вытащить из обновления (chat_id, токен, username), если это /start с токеном.

    Возвращает None на всём остальном: бот отвечает только на привязку.
    """
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    if not text.startswith("/start"):
        return None
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return None
    username = (message.get("from") or {}).get("username")
    return int(chat_id), parts[1].strip(), username
