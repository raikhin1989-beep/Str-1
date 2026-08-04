"""Регистрация гостей и привязка телеграма."""

import io
import json
import logging
from pathlib import Path

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Form, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app import auth, limits, models, scoring, telegram
from app.config import public_base_url

log = logging.getLogger("str1.join")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

router = APIRouter()


@router.get("/join/{code}")
def join_form(request: Request, code: str, error: str = ""):
    tasting = models.get_tasting_by_code(code)
    if tasting is None:
        raise HTTPException(status_code=404, detail="Дегустация не найдена")
    known = remembered(request)
    return templates.TemplateResponse(
        request,
        "join.html",
        {
            "tasting": tasting,
            "open": tasting["status"] == "registration",
            "status_title": models.STATUS_TITLES.get(tasting["status"], tasting["status"]),
            "error": error,
            # Тот же телефон уже открывал чью-то личную страницу — предложим
            # вернуться на неё, а не заводить второго участника с тем же именем.
            "known": known[0] if known else None,
            "known_token": known[1] if known else None,
        },
    )


@router.post("/join/{code}")
def join(request: Request, code: str, name: str = Form(""), contact: str = Form("")):
    tasting = models.get_tasting_by_code(code)
    if tasting is None:
        raise HTTPException(status_code=404, detail="Дегустация не найдена")
    try:
        limits.check("join", auth.client_ip(request))
    except limits.TooOften:
        return RedirectResponse(
            f"/join/{code}?error=Слишком много записей подряд, подождите немного",
            status_code=303,
        )
    try:
        token = models.register_participant(tasting["id"], name, contact)
    except ValueError as err:
        return RedirectResponse(f"/join/{code}?error={err}", status_code=303)
    return _remember(RedirectResponse(f"/me/{token}", status_code=303), request, token)


# Личная ссылка — единственный вход на свою страницу, и теряют её постоянно.
# Кладём токен в куку: тот же телефон найдёт свою страницу сам, даже если
# вкладка закрылась. Кука httponly — читать её из JS незачем, а вот утечь
# через чужой скрипт она не должна: это фактически пропуск.
ME_COOKIE = "str1_me"
ME_COOKIE_DAYS = 30


def _remember(response, request: Request, token: str):
    response.set_cookie(
        ME_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=auth.is_secure_request(request),
        max_age=60 * 60 * 24 * ME_COOKIE_DAYS,
        path="/",
    )
    return response


def remembered(request: Request):
    """Участник, чью страницу этот телефон открывал. None, если такого нет."""
    token = request.cookies.get(ME_COOKIE)
    if not token:
        return None
    participant = models.get_participant_by_token(token)
    return (participant, token) if participant else None


@router.get("/me/{token}")
def participant_page(request: Request, token: str, error: str = ""):
    participant = models.get_participant_by_token(token)
    if participant is None:
        raise HTTPException(status_code=404, detail="Участник не найден")
    tasting = models.get_tasting(participant["tasting_id"])
    round_name = models.open_round(tasting)

    context = {
        "participant": participant,
        "tasting": tasting,
        "linked": participant["tg_chat_id"] is not None,
        "deep_link": telegram.deep_link(token),
        "status_title": models.STATUS_TITLES.get(tasting["status"], tasting["status"]),
        "token": token,
        "my_url": _public_url(request, f"/me/{token}"),
        "round": round_name,
        # Состояние, с которым страница отрисована: скрипт сравнивает с ним
        # ответы опроса и перезагружает страницу, когда что-то изменилось.
        "state": {
            "status": tasting["status"],
            "round": round_name,
            "submitted": models.round_submitted(participant["id"], round_name)
            if round_name
            else False,
        },
        "waiting_for": _waiting_for(tasting["status"]),
        "error": error,
    }
    if tasting["status"] in models.RESULT_STATUSES:
        result = models.personal_result(participant["id"])
        score = models.score_tasting(tasting["id"]).get(participant["id"])
        whiskies = {row["id"]: row["name"] for row in models.round_choices(tasting["id"])}
        context |= {
            "result": result,
            "score": score,
            "whiskies": whiskies,
            "max_points": scoring.max_points(len(models.sample_numbers(tasting["id"]))),
            "code": tasting["public_code"],
        }

    if round_name:
        answers = models.get_answers(participant["id"], round_name)
        ratings = models.get_ratings(participant["id"])
        context |= {
            "round_title": models.ROUND_TITLES[round_name],
            "samples": models.sample_numbers(tasting["id"]),
            "choices": models.round_choices(tasting["id"]),
            "answers": answers,
            "ratings": {no: dict(row) for no, row in ratings.items()},
            "tags": {no: _tags_for(row, round_name) for no, row in ratings.items()},
            "submitted": models.round_submitted(participant["id"], round_name),
        }
    return _remember(templates.TemplateResponse(request, "me.html", context), request, token)


# Чего ждёт гость в каждом состоянии до итогов. None означает «ждать нечего».
_WAITING = {
    "draft": "Ведущий ещё готовит дегустацию.",
    "registration": "Все записываются. Скоро начнём.",
    "round_nose": None,
    "round_palate": None,
    "scoring": "Ведущий считает итоги.",
}


def _waiting_for(status: str) -> str | None:
    return _WAITING.get(status)


def _public_url(request: Request, path: str) -> str:
    """Адрес для показа гостю: домен важнее того, откуда открыта страница."""
    return (public_base_url() or str(request.base_url).rstrip("/")) + path


@router.get("/api/me/{token}/state")
def participant_state(token: str):
    """Что сейчас происходит — для страницы участника.

    Раунд открывает ведущий, а гость в это время смотрит в свой телефон.
    Без этого он видит «ждём» до тех пор, пока не догадается обновить
    страницу сам, — а за столом никто не догадывается.
    """
    participant = models.get_participant_by_token(token)
    if participant is None:
        raise HTTPException(status_code=404, detail="Участник не найден")
    tasting = models.get_tasting(participant["tasting_id"])
    round_name = models.open_round(tasting)
    return {
        "status": tasting["status"],
        "round": round_name,
        "submitted": models.round_submitted(participant["id"], round_name) if round_name else False,
    }


def _tags_for(rating, round_name: str) -> str:
    try:
        return json.loads(rating["tags"] or "{}").get(round_name, "")
    except ValueError:
        return ""


def _participant_in_round(token: str):
    """Участник, дегустация и открытый раунд — или отказ.

    Раунд берётся из статуса дегустации: из формы его принимать нельзя,
    иначе можно было бы отвечать во втором раунде, пока идёт первый.
    """
    participant = models.get_participant_by_token(token)
    if participant is None:
        raise HTTPException(status_code=404, detail="Участник не найден")
    tasting = models.get_tasting(participant["tasting_id"])
    round_name = models.open_round(tasting)
    if round_name is None:
        raise HTTPException(status_code=409, detail="Сейчас раунд не идёт")
    return participant, round_name


@router.post("/me/{token}/draft")
async def save_draft(request: Request, token: str):
    """Автосохранение черновика. Отвечает JSON — страница не перезагружается."""
    participant, round_name = _participant_in_round(token)
    try:
        limits.check("draft", auth.client_ip(request))
    except limits.TooOften:
        return JSONResponse({"ok": False, "error": "Слишком часто"}, status_code=429)
    payload = await request.json()
    try:
        models.save_round_draft(
            participant["id"],
            round_name,
            _int_map(payload.get("answers")),
            _int_map(payload.get("scores")),
            {int(k): str(v) for k, v in (payload.get("tags") or {}).items()},
        )
    except ValueError as err:
        return JSONResponse({"ok": False, "error": str(err)}, status_code=400)
    return {"ok": True}


@router.post("/me/{token}/submit")
async def submit(request: Request, token: str):
    """Отправка ответа. Форма присылает всё разом — на случай, если JS не сработал."""
    participant, round_name = _participant_in_round(token)
    form = await request.form()
    try:
        models.save_round_draft(
            participant["id"],
            round_name,
            _form_map(form, "sample_"),
            _form_map(form, "score_"),
            {
                int(key[len("tags_"):]): str(value)
                for key, value in form.items()
                if key.startswith("tags_")
            },
        )
        models.submit_round(participant["id"], round_name)
    except ValueError as err:
        return RedirectResponse(f"/me/{token}?error={err}", status_code=303)
    return RedirectResponse(f"/me/{token}", status_code=303)


def _int_map(raw) -> dict[int, int | None]:
    result: dict[int, int | None] = {}
    for key, value in (raw or {}).items():
        result[int(key)] = None if value in (None, "") else int(value)
    return result


def _form_map(form, prefix: str) -> dict[int, int | None]:
    result: dict[int, int | None] = {}
    for key, value in form.items():
        if not key.startswith(prefix):
            continue
        text = str(value).strip()
        result[int(key[len(prefix):])] = int(text) if text else None
    return result


@router.get("/results/{code}")
def results_page(request: Request, code: str):
    """Итоги вечера. До подведения — только сообщение, что рано."""
    tasting = models.get_tasting_by_code(code)
    if tasting is None:
        raise HTTPException(status_code=404, detail="Дегустация не найдена")
    ready = tasting["status"] in models.RESULT_STATUSES
    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "tasting": tasting,
            "ready": ready,
            "status_title": models.STATUS_TITLES.get(tasting["status"], tasting["status"]),
            "board": models.leaderboard(tasting["id"]) if ready else [],
            "samples": models.sample_breakdown(tasting["id"]) if ready else [],
            "best": models.whisky_of_the_night(tasting["id"]) if ready else None,
            "max_points": scoring.max_points(len(models.sample_numbers(tasting["id"]))),
            "code": code,
        },
    )


@router.get("/board/{code}")
def board_page(request: Request, code: str):
    """Экран ведущего: та же таблица крупно, сама обновляется."""
    tasting = models.get_tasting_by_code(code)
    if tasting is None:
        raise HTTPException(status_code=404, detail="Дегустация не найдена")
    return templates.TemplateResponse(
        request,
        "board.html",
        {"tasting": tasting, "code": code},
    )


@router.get("/api/board/{code}")
def board_data(code: str):
    """Данные для экрана ведущего. Пока идут раунды — счётчик сдавших."""
    tasting = models.get_tasting_by_code(code)
    if tasting is None:
        raise HTTPException(status_code=404, detail="Дегустация не найдена")
    round_name = models.open_round(tasting)
    done, total = models.round_progress(tasting["id"], round_name) if round_name else (0, 0)
    return {
        "title": tasting["title"],
        "status": models.STATUS_TITLES.get(tasting["status"], tasting["status"]),
        "round": models.ROUND_TITLES.get(round_name),
        "submitted": done,
        "participants": total,
        "rows": [
            {
                "place": row["place"],
                "name": row["name"],
                "nose": row["points_nose"],
                "palate": row["points_palate"],
                "partial": row["points_partial"],
                "bonus": row["points_bonus"],
                "total": row["total"],
            }
            for row in models.leaderboard(tasting["id"])
        ],
    }


@router.get("/qr.svg")
def qr(data: str):
    """QR-код для ссылки. SVG, потому что не требует ни Pillow, ни растра.

    Белый фон рисуется внутри самой картинки, а не задаётся стилем страницы:
    код сканируют с чужого экрана, картинку пересылают и пересохраняют, и
    прозрачный фон на тёмной теме превращает её в нечитаемое пятно.

    Поле в 4 модуля — по спецификации QR. С двумя, как было раньше, часть
    телефонов код не ловит: камере не за что зацепиться.
    """
    if len(data) > 512:
        raise HTTPException(status_code=400, detail="Слишком длинная ссылка")
    image = qrcode.make(
        data,
        image_factory=qrcode.image.svg.SvgPathFillImage,
        box_size=10,
        border=4,
    )
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
