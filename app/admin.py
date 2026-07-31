"""Админка: вход, дегустации, справочник виски."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import ai, auth, models
from app.config import admin_password

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
    return templates.TemplateResponse(
        request,
        "admin/tasting.html",
        {
            "tasting": tasting,
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
def change_status(tasting_id: int, status: str = Form(...)):
    try:
        models.set_status(tasting_id, status)
    except ValueError as err:
        return _redirect(f"/admin/tastings/{tasting_id}?error={err}")
    return _redirect(f"/admin/tastings/{tasting_id}?ok=Статус изменён")


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
def shuffle(tasting_id: int):
    try:
        models.shuffle_samples(tasting_id)
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
