"""Привязка участника к чату телеграма — одна логика на две дороги.

Сообщение от бота может прийти двумя путями:

* **вебхуком** — как задумано в Bot API. С этого сервера не работает:
  телеграм отвечает `Connection timed out`, блокировка двусторонняя;
* **через раннер GitHub** — он забирает сообщения у телеграма (getUpdates)
  и привозит их сюда. Это рабочий путь, тот же мост, что везёт итоги.

Обе дороги приводят сюда, чтобы правило связывания было одно. Если сеть
когда-нибудь откроется, вебхук заработает сам собой и ничего менять
не придётся.
"""

import logging

from app import models, telegram
from app.db import connect, log_action

log = logging.getLogger("str1.telegram_link")


def note(action: str, details: str) -> None:
    """Запись в журнал — то, что видно на странице «Телеграм» в админке."""
    with connect() as conn:
        log_action(conn, None, f"tg.{action}", details[:200])


def describe(update: dict) -> str:
    """Коротко, что пришло, — без пересказа чужой переписки.

    В журнал попадает только вид сообщения и первое слово команды: этого
    хватает, чтобы понять «нажали Старт без кода», и не хватает, чтобы
    прочитать, о чём человек писал боту.
    """
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    if not text:
        return "сообщение без текста"
    if text.startswith("/start"):
        return "Старт без кода" if len(text.split()) < 2 else "Старт с кодом"
    return "не команда Старт"


def apply(update: dict) -> str:
    """Связать участника с чатом. Возвращает, что произошло, — для журнала."""
    parsed = telegram.parse_start_command(update)
    if parsed is None:
        note("мимо", describe(update))
        return "мимо"

    chat_id, token, username = parsed
    participant = models.link_telegram(token, chat_id, username)
    note(
        "привязка" if participant else "чужой код",
        f"{participant['name'] if participant else 'код ' + token[:6] + '…'}"
        f"{', @' + username if username else ''}",
    )
    if participant is None:
        telegram.send_message(
            chat_id,
            "Не нашёл, к кому вас привязать. Откройте ссылку регистрации ещё раз "
            "и нажмите кнопку «Привязать телеграм».",
        )
        return "чужой код"

    tasting = models.get_tasting(participant["tasting_id"])
    telegram.send_message(
        chat_id,
        f"Готово, {participant['name']}! Пришлю сюда итоги дегустации "
        f"«{tasting['title']}».",
    )
    return "привязка"
