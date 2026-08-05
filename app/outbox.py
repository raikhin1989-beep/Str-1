"""Мост между приложением и телеграмом: и туда, и обратно.

Зачем это существует: сервер и api.telegram.org не видят друг друга **ни
в одну сторону**. Исходящие с сервера не проходят — это было известно
и проверено. Про входящие считалось, что они идут, и на этом держалась вся
привязка участников; 5 августа выяснилось, что это неверно. getWebhookInfo
у самого телеграма ответил `Connection timed out`: вебхук зарегистрирован,
а доставить по нему не получается. Блокировка двусторонняя.

Поэтому и рассылка, и привязка ходят через раннер GitHub, у которого доступ
к телеграму есть:

* **итоги** — приложение готовит сообщения, раннер забирает, отправляет
  и докладывает, что дошло. Отметка ставится только по докладу;
* **привязка** — раннер забирает у телеграма пришедшие боту сообщения
  (getUpdates) и отдаёт их сюда; связывание участника с чатом делает
  приложение, как делало бы по вебхуку.

Доступ по секрету вебхука. Отдельный секрет заводить не стали: этот уже
случайный, уже есть у раннера, и утечка любого из них означает одно и то же —
чужой может писать участникам от имени бота.
"""

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request

from app import broadcast, models, telegram
from app import telegram_link
from app.config import public_base_url

log = logging.getLogger("str1.outbox")

router = APIRouter(prefix="/internal/outbox")


def _check(secret: str) -> None:
    expected = telegram.webhook_secret()
    # Сравниваем байтами: compare_digest не принимает строки с не-ASCII,
    # а в адрес может прийти что угодно — на этом уже спотыкались в auth.py.
    # 404, а не 403: посторонний не должен узнать, что такой путь вообще есть.
    if not expected or not hmac.compare_digest(secret.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=404, detail="Not Found")


@router.get("/{secret}")
def outbox(request: Request, secret: str):
    """Что осталось разослать по последней посчитанной дегустации."""
    _check(secret)
    tasting_id = broadcast.latest_scored_tasting()
    if tasting_id is None:
        return {"tasting": None, "messages": []}

    tasting = models.get_tasting(tasting_id)
    base = public_base_url() or str(request.base_url).rstrip("/")
    messages = broadcast.pending(tasting_id, f"{base}/results/{tasting['public_code']}")
    return {"tasting": tasting["title"], "count": len(messages), "messages": messages}


@router.post("/{secret}/delivered")
async def mark(request: Request, secret: str):
    """Отметить доставленные. Тело: {"ids": [...]}."""
    _check(secret)
    payload = await request.json()
    ids = [int(value) for value in (payload.get("ids") or [])]
    for participant_id in ids:
        models.mark_delivered(participant_id, broadcast.KIND)
    log.info("итоги доставлены участникам: %s", ids)
    return {"ok": True, "marked": len(ids)}



# ── привязка: обновления, привезённые раннером ─────────────────────────────


@router.post("/{secret}/updates")
async def incoming(request: Request, secret: str):
    """Обработать сообщения, которые бот получил, а мы забрать не смогли.

    Тело: {"updates": [ ... как их отдаёт getUpdates ... ]}. Разбор и
    связывание — те же, что у вебхука: сюда приходит ровно то, что пришло бы
    по нему, только другой дорогой. Ответ говорит, что с каждым сообщением
    произошло, — это и есть журнал на странице «Телеграм» в админке.
    """
    _check(secret)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="ожидался объект")
    handled = []
    for update in payload.get("updates") or []:
        if isinstance(update, dict):
            handled.append(telegram_link.apply(update))
    log.info("привезено обновлений: %s", len(handled))
    return {"ok": True, "handled": handled}
