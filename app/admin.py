"""Админка: вход, дегустации, справочник виски."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from app import ai, auth, backup, broadcast, models, telegram
from app.config import admin_password, public_base_url
from app.db import connect, log_action

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

router = APIRouter(prefix="/admin")


def require_admin(request: Request) -> None:
    """Пускать только с живой сессией, иначе — на форму входа."""
    if not auth.session_is_valid(request.cookies.get(auth.COOKIE_NAME)):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})


def _redirect(url: str) -> RedirectResponse:
    # 303: после POST браузер должен перейти на страницу методом GET,
    # иначе обновление страницы повторит действие.
    return RedirectResponse(url, status_code=303)


def _public(request: Request, path: str) -> str:
    """Ссылка для гостей. Публичный адрес важнее того, где открыта админка."""
    base = public_base_url() or str(request.base_url).rstrip("/")
    return f"{base}{path}"


def _note(request: Request, action: str, details: str = "") -> None:
    """Записать действие админа в журнал.

    Нужно ровно для одного разговора: «а кто закрыл раунд?» — вечером
    за столом это выясняется быстрее, чем по памяти.
    """
    with connect() as conn:
        log_action(conn, auth.client_ip(request), action, details)


# ── вход ───────────────────────────────────────────────────────────────────


@router.get("/login")
def login_form(request: Request):
    if not admin_password():
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"disabled": True, "error": "Админка выключена: на сервере не задан ADMIN_PASSWORD."},
            status_code=503,
        )
    if auth.session_is_valid(request.cookies.get(auth.COOKIE_NAME)):
        return _redirect("/admin/tastings")
    return templates.TemplateResponse(request, "admin/login.html", {})


@router.post("/login")
def login(request: Request, password: str = Form("")):
    ip = auth.client_ip(request)

    locked = auth.is_locked_out(ip)
    if locked:
        minutes = max(1, locked // 60)
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"error": f"Слишком много попыток. Попробуйте через {minutes} мин."},
            status_code=429,
        )

    if not auth.password_matches(password):
        auth.note_failure(ip)
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"error": "Неверный пароль."},
            status_code=401,
        )

    auth.reset_failures(ip)
    token = auth.start_session(ip)
    response = _redirect("/admin/tastings")
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        secure=auth.is_secure_request(request),
        max_age=60 * 60 * 24 * 14,
        path="/",
    )
    return response


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        auth.end_session(token, auth.client_ip(request))
    response = _redirect("/admin/login")
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return response


# ── дегустации ─────────────────────────────────────────────────────────────


@router.get("", dependencies=[Depends(require_admin)])
def admin_root():
    return _redirect("/admin/tastings")


@router.get("/tastings", dependencies=[Depends(require_admin)])
def tastings_page(request: Request, error: str = "", ok: str = ""):
    return templates.TemplateResponse(
        request,
        "admin/tastings.html",
        {
            "tastings": models.list_tastings(),
            "statuses": models.STATUS_TITLES,
            "levels": models.CATEGORY_LEVELS,
            "error": error,
            "ok": ok,
        },
    )


@router.post("/tastings", dependencies=[Depends(require_admin)])
def create_tasting(
    title: str = Form(...),
    held_on: str = Form(""),
    category_level: str = Form("class"),
):
    try:
        tasting_id = models.create_tasting(title, held_on, category_level)
    except ValueError as err:
        return _redirect(f"/admin/tastings?error={err}")
    return _redirect(f"/admin/tastings/{tasting_id}")


@router.get("/tastings/{tasting_id}", dependencies=[Depends(require_admin)])
def tasting_page(request: Request, tasting_id: int, error: str = "", ok: str = ""):
    tasting = models.get_tasting(tasting_id)
    if tasting is None:
        raise HTTPException(status_code=404, detail="Дегустация не найдена")
    in_tasting = models.tasting_whiskies(tasting_id)
    chosen = {row["id"] for row in in_tasting}
    # Ссылки для гостей — от публичного адреса (см. _public): админку могут
    # открыть и по запасному входу на 8081, а гостю нужен домен.
    join_url = _public(request, f"/join/{tasting['public_code']}")
    round_name = models.open_round(tasting)
    done, total = models.round_progress(tasting_id, round_name) if round_name else (0, 0)
    return templates.TemplateResponse(
        request,
        "admin/tasting.html",
        {
            "tasting": tasting,
            "round": round_name,
            "round_title": models.ROUND_TITLES.get(round_name, ""),
            "round_done": done,
            "round_total": total,
            "scored": tasting["status"] in models.RESULT_STATUSES,
            "board": models.leaderboard(tasting_id),
            "summary": broadcast.summary_text(
                tasting,
                models.leaderboard(tasting_id),
                _public(request, f"/results/{tasting['public_code']}"),
            ),
            "results_url": _public(request, f"/results/{tasting['public_code']}"),
            "board_url": _public(request, f"/board/{tasting['public_code']}"),
            "participants": models.list_participants(tasting_id),
            # Личные ссылки гостей: ссылку теряют чаще всего, и восстановить
            # её должен уметь ведущий, а не тот, кто ходит в базу.
            # Совпадения по контакту с прошлыми дегустациями: связывать
            # автоматически нельзя (контакт пишет сам гость), поэтому это
            # подсказка с кнопкой — решает ведущий, он знает, кто за столом.
            "matches": {
                person["id"]: models.matching_telegram(tasting_id, person["id"])
                for person in models.list_participants(tasting_id)
            },
            "me_urls": {
                person["id"]: _public(request, f"/me/{person['join_token']}")
                for person in models.list_participants(tasting_id)
            },
            "join_url": join_url,
            "samples": in_tasting,
            "catalogue": [w for w in models.list_whiskies() if w["id"] not in chosen],
            "statuses": models.STATUS_TITLES,
            "levels": models.CATEGORY_LEVELS,
            "next_statuses": models.ALLOWED_TRANSITIONS.get(tasting["status"], []),
            "editable": tasting["status"] in models.EDITABLE_STATUSES,
            "error": error,
            "ok": ok,
        },
    )


@router.post("/tastings/{tasting_id}", dependencies=[Depends(require_admin)])
def update_tasting(
    tasting_id: int,
    title: str = Form(...),
    held_on: str = Form(""),
    category_level: str = Form("class"),
):
    try:
        models.update_tasting(tasting_id, title, held_on, category_level)
    except ValueError as err:
        return _redirect(f"/admin/tastings/{tasting_id}?error={err}")
    return _redirect(f"/admin/tastings/{tasting_id}?ok=Сохранено")


@router.post("/tastings/{tasting_id}/status", dependencies=[Depends(require_admin)])
def change_status(request: Request, tasting_id: int, status: str = Form(...)):
    try:
        models.set_status(tasting_id, status)
    except ValueError as err:
        return _redirect(f"/admin/tastings/{tasting_id}?error={err}")
    # Переход к подсчёту сразу считает: иначе между «итоги подведены» и первым
    # нажатием «пересчитать» страница итогов стояла бы пустой.
    if status in models.RESULT_STATUSES:
        models.compute_results(tasting_id)
    _note(request, "tasting.status", f"дегустация {tasting_id} → {status}")
    return _redirect(f"/admin/tastings/{tasting_id}?ok=Статус изменён")


@router.get("/telegram", dependencies=[Depends(require_admin)])
def telegram_page(request: Request):
    """Что происходит с ботом.

    Существует ради одного вопроса: «я нажал Старт, почему не привязалось?».
    Ответ виден в журнале: если записей нет вовсе — телеграм до нас не дошёл;
    если стоит «Старт без кода» — человек написал боту сам, а не открыл свою
    ссылку привязки.
    """
    with connect() as conn:
        events = conn.execute(
            "SELECT at, action, details FROM audit_log"
            " WHERE action LIKE 'tg.%' ORDER BY id DESC LIMIT 30"
        ).fetchall()
    return templates.TemplateResponse(
        request,
        "admin/telegram.html",
        {
            "events": events,
            "bot": telegram.known_username(),
            "configured": telegram.is_configured(),
            "hook_path": "/tg/<секрет вебхука>",
        },
    )


@router.post(
    "/tastings/{tasting_id}/participants/{participant_id}/carry",
    dependencies=[Depends(require_admin)],
)
def carry_telegram(request: Request, tasting_id: int, participant_id: int):
    """Перенести телеграм с прошлой дегустации — по решению ведущего."""
    match = models.matching_telegram(tasting_id, participant_id)
    if match is None:
        return _redirect(f"/admin/tastings/{tasting_id}?error=Совпадения больше нет")
    models.carry_over_telegram(match["id"], participant_id)
    _note(request, "tasting.carry", f"участник {participant_id} ← {match['id']}")
    return _redirect(f"/admin/tastings/{tasting_id}?ok=Телеграм перенесён")


@router.get("/backup", dependencies=[Depends(require_admin)])
def download_backup(request: Request):
    """Скачать свежую копию базы.

    Копия снимается прямо сейчас и во временный файл, а не берётся из
    /var/backups: скачивают её обычно как раз тогда, когда нужен слепок
    на эту минуту, а не вчерашний.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = Path(tempfile.gettempdir()) / f"str-1-{stamp}.db"
    backup.snapshot(target)
    with connect() as conn:
        log_action(conn, auth.client_ip(request), "admin.backup", target.name)
    return FileResponse(
        target,
        media_type="application/octet-stream",
        filename=f"str-1-{stamp}.db",
        # Файл удаляем после отдачи: во временном каталоге копия базы
        # со всеми ответами участников залёживаться не должна.
        background=BackgroundTask(target.unlink),
    )


@router.post("/tastings/{tasting_id}/broadcast", dependencies=[Depends(require_admin)])
def send_results(request: Request, tasting_id: int):
    """Разослать итоги в телеграм. Повторное нажатие догоняет только тех, кому не дошло."""
    tasting = models.get_tasting(tasting_id)
    if tasting is None:
        raise HTTPException(status_code=404, detail="Дегустация не найдена")
    url = _public(request, f"/results/{tasting['public_code']}")
    try:
        report = broadcast.send_results(tasting_id, url)
    except ValueError as err:
        return _redirect(f"/admin/tastings/{tasting_id}?error={err}")

    parts = [f"отправлено: {len(report['sent'])}"]
    for label, key in (("уже было", "skipped"), ("без телеграма", "unlinked"), ("не дошло", "failed")):
        if report[key]:
            parts.append(f"{label}: {', '.join(report[key])}")
    _note(request, "tasting.broadcast", f"дегустация {tasting_id}: {'; '.join(parts)}")
    return _redirect(f"/admin/tastings/{tasting_id}?ok=Рассылка — {'; '.join(parts)}")


@router.post("/tastings/{tasting_id}/recount", dependencies=[Depends(require_admin)])
def recount(request: Request, tasting_id: int):
    """Пересчитать итоги. Таблица — кэш, поэтому жать можно сколько угодно."""
    tasting = models.get_tasting(tasting_id)
    if tasting is None or tasting["status"] not in models.RESULT_STATUSES:
        return _redirect(f"/admin/tastings/{tasting_id}?error=Сначала подведите итоги")
    models.compute_results(tasting_id)
    _note(request, "tasting.recount", f"дегустация {tasting_id}")
    return _redirect(f"/admin/tastings/{tasting_id}?ok=Пересчитано")


@router.post("/tastings/{tasting_id}/samples", dependencies=[Depends(require_admin)])
def add_sample(tasting_id: int, whisky_id: int = Form(...)):
    try:
        models.add_whisky_to_tasting(tasting_id, whisky_id)
    except ValueError as err:
        return _redirect(f"/admin/tastings/{tasting_id}?error={err}")
    return _redirect(f"/admin/tastings/{tasting_id}?ok=Виски добавлен")


@router.post("/tastings/{tasting_id}/samples/{whisky_id}/remove", dependencies=[Depends(require_admin)])
def remove_sample(tasting_id: int, whisky_id: int):
    try:
        models.remove_whisky_from_tasting(tasting_id, whisky_id)
    except ValueError as err:
        return _redirect(f"/admin/tastings/{tasting_id}?error={err}")
    return _redirect(f"/admin/tastings/{tasting_id}?ok=Виски убран")


@router.post("/tastings/{tasting_id}/shuffle", dependencies=[Depends(require_admin)])
def shuffle(request: Request, tasting_id: int):
    try:
        models.shuffle_samples(tasting_id)
        _note(request, "tasting.shuffle", f"дегустация {tasting_id}")
    except ValueError as err:
        return _redirect(f"/admin/tastings/{tasting_id}?error={err}")
    return _redirect(f"/admin/tastings/{tasting_id}?ok=Номера перемешаны")


# ── справочник виски ───────────────────────────────────────────────────────


@router.get("/whiskies", dependencies=[Depends(require_admin)])
def whiskies_page(request: Request, error: str = "", ok: str = ""):
    return templates.TemplateResponse(
        request,
        "admin/whiskies.html",
        {
            "whiskies": models.list_whiskies(),
            "classes": models.WHISKY_CLASSES,
            "error": error,
            "ok": ok,
        },
    )


@router.post("/whiskies", dependencies=[Depends(require_admin)])
async def create_whisky(request: Request):
    form = dict(await request.form())
    try:
        whisky_id = models.save_whisky(form)
    except ValueError as err:
        return _redirect(f"/admin/whiskies?error={err}")
    return _redirect(f"/admin/whiskies/{whisky_id}?ok=Добавлено")


@router.post("/whiskies/import", dependencies=[Depends(require_admin)])
def import_whisky_from_ai(cache_key: str = Form(...)):
    """Сохранить в справочник карточку, полученную от модели.

    Берём её из кэша по ключу, а не из формы: так в базу попадает ровно то, что
    ответила модель, и подменить поля через скрытые input'ы нельзя.
    """
    card = ai.cached_card(cache_key)
    if card is None:
        return _redirect("/admin/whiskies?error=Карточка не найдена, распознайте заново")
    try:
        whisky_id = models.save_whisky(card, source="ai")
    except ValueError as err:
        return _redirect(f"/admin/whiskies?error={err}")
    return _redirect(f"/admin/whiskies/{whisky_id}?ok=Добавлено из распознавания — проверьте поля")


@router.get("/whiskies/{whisky_id}", dependencies=[Depends(require_admin)])
def whisky_page(request: Request, whisky_id: int, error: str = "", ok: str = ""):
    whisky = models.get_whisky(whisky_id)
    if whisky is None:
        raise HTTPException(status_code=404, detail="Виски не найден")
    return templates.TemplateResponse(
        request,
        "admin/whisky.html",
        {"whisky": whisky, "classes": models.WHISKY_CLASSES, "error": error, "ok": ok},
    )


@router.post("/whiskies/{whisky_id}", dependencies=[Depends(require_admin)])
async def update_whisky(request: Request, whisky_id: int):
    form = dict(await request.form())
    try:
        models.save_whisky(form, whisky_id=whisky_id)
    except ValueError as err:
        return _redirect(f"/admin/whiskies/{whisky_id}?error={err}")
    return _redirect(f"/admin/whiskies/{whisky_id}?ok=Сохранено")
