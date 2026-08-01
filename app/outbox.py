"""Исходящие сообщения для того, кто может их доставить.

Зачем это существует: с этого сервера исходящие соединения к api.telegram.org
не проходят — проверено, TCP-таймаут. Входящие идут (вебхук работает), поэтому
привязка участников жива, а рассылка итогов — нет.

Решение: сообщения готовит приложение, а отвозит их раннер GitHub, у которого
доступ к телеграму есть. Он забирает список отсюда, отправляет и сообщает,
что дошло. Отметка о доставке ставится только по его ответу — то же правило,
что и при прямой отправке.

Доступ по секрету вебхука. Отдельный секрет заводить не стали: этот уже
случайный, уже есть у раннера, и утечка любого из них означает одно и то же —
чужой может писать участникам от имени бота.
"""

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request

from app import broadcast, models, telegram
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
