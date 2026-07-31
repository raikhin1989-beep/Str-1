"""Регистрация гостей и привязка телеграма."""

import io
import logging
from pathlib import Path

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Form, Header, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app import models, telegram

log = logging.getLogger("str1.join")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

router = APIRouter()


@router.get("/join/{code}")
def join_form(request: Request, code: str, error: str = ""):
    tasting = models.get_tasting_by_code(code)
    if tasting is None:
        raise HTTPException(status_code=404, detail="Дегустация не найдена")
    return templates.TemplateResponse(
        request,
        "join.html",
        {
            "tasting": tasting,
            "open": tasting["status"] == "registration",
            "status_title": models.STATUS_TITLES.get(tasting["status"], tasting["status"]),
            "error": error,
        },
    )


@router.post("/join/{code}")
def join(code: str, name: str = Form("")):
    tasting = models.get_tasting_by_code(code)
    if tasting is None:
        raise HTTPException(status_code=404, detail="Дегустация не найдена")
    try:
        token = models.register_participant(tasting["id"], name)
    except ValueError as err:
        return RedirectResponse(f"/join/{code}?error={err}", status_code=303)
    return RedirectResponse(f"/me/{token}", status_code=303)


@router.get("/me/{token}")
def participant_page(request: Request, token: str):
    participant = models.get_participant_by_token(token)
    if participant is None:
        raise HTTPException(status_code=404, detail="Участник не найден")
    tasting = models.get_tasting(participant["tasting_id"])
    return templates.TemplateResponse(
        request,
        "me.html",
        {
            "participant": participant,
            "tasting": tasting,
            "linked": participant["tg_chat_id"] is not None,
            "deep_link": telegram.deep_link(token),
            "status_title": models.STATUS_TITLES.get(tasting["status"], tasting["status"]),
        },
    )


@router.get("/qr.svg")
def qr(data: str):
    """QR-код для ссылки. SVG, потому что не требует ни Pillow, ни растра."""
    if len(data) > 512:
        raise HTTPException(status_code=400, detail="Слишком длинная ссылка")
    image = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    return Response(
        buffer.getvalue(),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/tg/{secret}")
async def telegram_webhook(
    request: Request,
    secret: str,
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    """Приём обновлений от телеграма.

    Проверяем секрет дважды — и в пути, и в заголовке, который телеграм
    присылает сам. Без этого кто угодно мог бы прислать поддельное «пользователь
    нажал Start» и привязать чужой аккаунт к участнику.
    """
    expected = telegram.webhook_secret()
    if not expected or secret != expected or x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=404, detail="Not Found")

    update = await request.json()
    parsed = telegram.parse_start_command(update)
    if parsed is None:
        # Не привязка — молча соглашаемся: телеграм повторяет обновления,
        # на которые ответили ошибкой.
        return {"ok": True}

    chat_id, token, username = parsed
    participant = models.link_telegram(token, chat_id, username)
    if participant is None:
        telegram.send_message(
            chat_id,
            "Не нашёл, к кому вас привязать. Откройте ссылку регистрации ещё раз "
            "и нажмите кнопку «Привязать телеграм».",
        )
        return {"ok": True}

    tasting = models.get_tasting(participant["tasting_id"])
    telegram.send_message(
        chat_id,
        f"Готово, {participant['name']}! Пришлю сюда итоги дегустации "
        f"«{tasting['title']}».",
    )
    return {"ok": True}
