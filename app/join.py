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

from app import auth, limits, models, scoring, telegram, telegram_link
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
    # Та же дегустация — предложить вернуться на свою страницу. Другая —
    # это гость, который пришёл во второй раз: подставим ему имя и контакт,
    # чтобы не набирать заново.
    here = known if known and known[0]["tasting_id"] == tasting["id"] else None
    before = known if known and here is None else None
    # Ссылку регистрации открывают и после вечера — по старому QR, из чата,
    # из закладки. Показывать «записаться нельзя» и всё — тупик: человек
    # пришёл по ссылке этой дегустации, значит ему нужны её итоги.
    finished = tasting["status"] in models.RESULT_STATUSES
    return templates.TemplateResponse(
        request,
        "join.html",
        {
            "tasting": tasting,
            "open": tasting["status"] == "registration",
            "finished": finished,
            "board": models.leaderboard(tasting["id"]) if finished else [],
            "status_title": models.STATUS_TITLES.get(tasting["status"], tasting["status"]),
            "error": error,
            "known": here[0] if here else None,
            "known_token": here[1] if here else None,
            "before": before[0] if before else None,
            "before_linked": bool(before and before[0]["tg_chat_id"]),
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
    known = remembered(request)
    try:
        token = models.register_participant(tasting["id"], name, contact)
    except ValueError as err:
        return RedirectResponse(f"/join/{code}?error={err}", status_code=303)

    # Второй раз на дегустации — телеграм переносим сам. Основание: это тот же
    # телефон, который открывал прошлую запись. Возиться с ботом повторно
    # человек не должен, а по строчке контакта связывать нельзя — см. models.
    if known and known[0]["tasting_id"] != tasting["id"]:
        new_id = models.get_participant_by_token(token)["id"]
        if models.carry_over_telegram(known[0]["id"], new_id):
            telegram_link.note("перенос", f"{name}: телеграм с прошлой дегустации")

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


@router.post("/me/{token}")
def participant_page_posted(token: str):
    """Случайный POST на адрес страницы — не тупик, а сама страница.

    Голый 405 посреди вечера выглядит как сломанный сайт, а починить его
    гость не может: он не знает ни что нажал, ни что делать. Отправлять
    ответы сюда всё равно нечем — форма шлёт на /submit, — так что здесь
    остаётся только показать человеку его страницу в актуальном виде.
    """
    return RedirectResponse(f"/me/{token}", status_code=303)


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
        # Имя бота нужно и запасному пути «отправьте код сообщением».
        "bot_name": telegram.known_username(),
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
            "linked": participant["tg_chat_id"] is not None,
        },
        "waiting_for": _waiting_for(tasting["status"]),
        # «за класс» на дегустации по регионам — враньё в глаза. Подпись
        # везде идёт от того, как заведена дегустация.
        "category_title": _category_title(tasting),
        "error": error,
    }
    if tasting["status"] in models.RESULT_STATUSES:
        context["finished"] = True
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
        choices = models.round_choices(tasting["id"])
        context |= {
            "round_title": models.ROUND_TITLES[round_name],
            "samples": models.sample_numbers(tasting["id"]),
            "choices": choices,
            "choice_groups": models.grouped_choices(choices),
            "wide_choice": tasting["answer_scope"] == "catalogue",
            "answers": answers,
            # Прямой ответ «а какой это хотя бы класс»: даёт тот же частичный
            # балл и нужен тому, кто уверен в классе, но винокурню не вспомнит.
            "categories": models.get_categories(participant["id"], round_name),
            "category_choices": models.category_choices(tasting["category_level"]),
            # Оценка своя на каждый раунд: попробовав, человек часто меняет
            # мнение, и показывать ему в раунде вкуса то, что он поставил
            # по запаху, — значит и сбивать, и подсказывать.
            "scores": models.get_scores(participant["id"], round_name),
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
        # Привязку телеграма страница обязана заметить сама. Гость уходит
        # к боту, жмёт «Старт» и возвращается — а ответного сообщения от бота
        # не будет: исходящие с этого сервера не проходят. Единственный, кто
        # может сказать «получилось», — эта страница. Пока привязки здесь
        # не было, она молчала и продолжала просить сделать то, что уже
        # сделано; на живом тесте это и выглядело как «привязка не работает».
        "linked": participant["tg_chat_id"] is not None,
    }


def _category_title(tasting) -> str:
    return "регион" if tasting["category_level"] == "region" else "класс"


def _tags_for(rating, round_name: str) -> str:
    try:
        return json.loads(rating["tags"] or "{}").get(round_name, "")
    except ValueError:
        return ""


def _participant_in_round(token: str, came_from: str = ""):
    """Участник, дегустация и открытый раунд — или отказ.

    Раунд для записи берётся из статуса дегустации: принимать его из формы
    нельзя, иначе можно было бы отвечать во втором раунде, пока идёт первый.

    А вот сверить с формой — обязательно, и это дорого далось. Гость держит
    страницу раунда по запаху открытой, ведущий тем временем открывает вкус,
    гость дожимает «Отправить» — и его ответ по запаху молча ложится в раунд
    вкуса. Настоящего ответа по вкусу он больше не даст: отправленное
    заморожено. Так на живой дегустации 5 августа и «потерялся» ответ.

    Страница обычно перерисовывается сама (см. me.js), но связь на вечеринке
    пропадает, вкладка засыпает, телефон блокируется — надеяться на это нельзя.
    Поэтому расхождение ловим на сервере и говорим человеку, что произошло.
    """
    participant = models.get_participant_by_token(token)
    if participant is None:
        raise HTTPException(status_code=404, detail="Участник не найден")
    tasting = models.get_tasting(participant["tasting_id"])
    round_name = models.open_round(tasting)
    if round_name is None:
        raise HTTPException(status_code=409, detail="Сейчас раунд не идёт")
    if came_from and came_from != round_name:
        raise HTTPException(
            status_code=409,
            detail=(
                "Пока вы отвечали, ведущий перешёл к другому раунду — "
                f"сейчас идёт «{models.ROUND_TITLES.get(round_name, round_name)}». "
                "Страница сейчас обновится, ответьте заново."
            ),
        )
    return participant, round_name


@router.post("/me/{token}/draft")
async def save_draft(request: Request, token: str):
    """Автосохранение черновика. Отвечает JSON — страница не перезагружается."""
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse({"ok": False, "error": "Не разобрал запрос"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"ok": False, "error": "Не разобрал запрос"}, status_code=400)
    try:
        participant, round_name = _participant_in_round(token, str(payload.get("round") or ""))
    except HTTPException as err:
        # Черновик отвечает JSON: страница не перезагружается, и скрипту
        # надо сказать словами, что случилось.
        return JSONResponse({"ok": False, "error": err.detail}, status_code=err.status_code)
    try:
        # По личной ссылке, а не по адресу: за одним роутером сидит весь стол,
        # и счёт по адресу останавливал сохранение сразу всем — у кого раньше
        # кончилась квота, тот и виноват. Токен — это ровно один гость.
        limits.check("draft", token)
    except limits.TooOften:
        return JSONResponse({"ok": False, "error": "Слишком часто"}, status_code=429)
    try:
        models.save_round_draft(
            participant["id"],
            round_name,
            _int_map(payload.get("answers")),
            _int_map(payload.get("scores")),
            _tag_map(payload.get("tags")),
            _tag_map(payload.get("categories")),
        )
    except ValueError as err:
        return JSONResponse({"ok": False, "error": str(err)}, status_code=400)
    return {"ok": True}


@router.post("/me/{token}/submit")
async def submit(request: Request, token: str):
    """Отправка ответа. Форма присылает всё разом — на случай, если JS не сработал."""
    form = await request.form()
    participant, round_name = _participant_in_round(token, str(form.get("round") or ""))
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
            {
                int(key[len("class_"):]): str(value)
                for key, value in form.items()
                if key.startswith("class_")
            },
        )
        models.submit_round(participant["id"], round_name)
    except ValueError as err:
        return RedirectResponse(f"/me/{token}?error={err}", status_code=303)
    return RedirectResponse(f"/me/{token}", status_code=303)


def _whole(value) -> int:
    """Целое из чего угодно, что пришло снаружи.

    Всё, что не число, — ValueError: выше он превращается в честный ответ
    «так нельзя». Раньше сюда прилетали список и слишком длинное число,
    а int() отвечал на них TypeError и OverflowError — они мимо обработчика
    и роняли запрос пятисоткой.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("ожидалось число")
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError) as err:
        raise ValueError("ожидалось число") from err
    # SQLite хранит 8 байт со знаком; всё, что больше, роняло вставку
    # OverflowError уже внутри транзакции.
    if not -(2**63) <= number < 2**63:
        raise ValueError("число слишком большое")
    return number


def _tag_map(raw) -> dict[int, str]:
    if not isinstance(raw, dict):
        if raw in (None, ""):
            return {}
        raise ValueError("ожидался объект")
    # Значение приводим к строке сами: словарь или список тут не ошибка
    # запроса, а просто не заметка, и падать из-за него незачем.
    return {_whole(key): str(value) for key, value in raw.items()}


def _int_map(raw) -> dict[int, int | None]:
    # Тело запроса пишет браузер, но прислать сюда можно что угодно — от
    # строки до вложенного объекта. Всё непохожее на словарь считаем пустым.
    if not isinstance(raw, dict):
        if raw in (None, ""):
            return {}
        raise ValueError("ожидался объект")
    result: dict[int, int | None] = {}
    for key, value in raw.items():
        result[_whole(key)] = None if value in (None, "") else _whole(value)
    return result


def _form_map(form, prefix: str) -> dict[int, int | None]:
    result: dict[int, int | None] = {}
    for key, value in form.items():
        if not key.startswith(prefix):
            continue
        text = str(value).strip()
        result[_whole(key[len(prefix):])] = _whole(text) if text else None
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
            "category_title": _category_title(tasting),
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
        telegram_link.note("отказ", "секрет не совпал")
        raise HTTPException(status_code=404, detail="Not Found")

    # Разбор и связывание — общие с тем путём, которым обновления привозит
    # раннер (app/telegram_link.py). Здесь остаётся только проверка секрета:
    # сюда может постучаться кто угодно.
    telegram_link.apply(await request.json())
    return {"ok": True}
