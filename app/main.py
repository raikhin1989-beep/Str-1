"""Точка входа приложения дегустации виски.

Слушает 127.0.0.1:8082 и наружу не торчит: снаружи всё приходит через Caddy,
который отдаёт /healthz, /version и /static сам файлами, а остальное проксирует
сюда. Разделение описано в docs/ARCHITECTURE.md.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import ai, telegram
from app.admin import router as admin_router
from app.config import admin_password
from app.join import router as join_router
from app.public import router as public_router

log = logging.getLogger("str1.app")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Схему OpenAPI и интерактивную документацию не публикуем: это не публичное API,
# а сайт для гостей дегустации.
app = FastAPI(
    title="Дегустация виски",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


app.include_router(public_router)
app.include_router(join_router)
app.include_router(admin_router)


@app.get("/api/health")
def health() -> dict:
    """Живо ли приложение и какие функции включены.

    Отдельно от /healthz: тот отдаётся файлом и проверяет, что доехал деплой.
    Этот отвечает, только если работает сам процесс приложения.

    Флаги показывают, доехали ли секреты до приложения, — сами значения,
    разумеется, не отдаются. Без этого потерянный по дороге секрет выключал бы
    функцию молча, а деплой рапортовал бы об успехе.
    """
    return {
        "status": "ok",
        "admin": bool(admin_password()),
        "ai": ai.is_configured(),
        "ai_provider": ai.provider(),
        "ai_photo": ai.supports_images(),
        "telegram": telegram.is_configured(),
        # Имя бота: без него не собрать ссылку привязки, и гость
        # видит «бот недоступен». Проще проверить здесь, чем гадать.
        "telegram_bot": telegram.bot_username(),
    }


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


# ── страницы ошибок ────────────────────────────────────────────────────────
#
# Гость не должен видеть ни голого «Internal Server Error», ни JSON с полем
# detail: он не поймёт, что делать, и решит, что сломался весь вечер.
# Внутренним запросам (админка, JSON-ручки) по-прежнему нужен JSON — их
# отличаем по заголовку Accept.

TROUBLE = {
    404: ("Такой страницы нет", "Проверьте ссылку — возможно, она устарела или в ней опечатка."),
    409: ("Сейчас так нельзя", "Похоже, раунд уже закрыт или ещё не начался. Обновите страницу."),
    429: ("Слишком часто", "Подождите минуту и попробуйте снова."),
    500: ("Что-то сломалось", "Мы уже знаем: ошибка записана в журнал. Попробуйте обновить страницу."),
}


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


def _trouble(request: Request, code: int, detail: str = ""):
    title, hint = TROUBLE.get(code, ("Ошибка", "Попробуйте обновить страницу."))
    # Свои сообщения мы пишем по-русски, а стандартные тексты Starlette —
    # английские («Not Found»). Гостю от них никакой пользы, поэтому берём
    # detail, только если он наш.
    if detail and any("а" <= letter.lower() <= "я" for letter in detail):
        hint = detail
    return templates.TemplateResponse(
        request,
        "error.html",
        {"code": code, "trouble": title, "hint": hint},
        status_code=code,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    # Редиректы через исключение (так админка отправляет на форму входа)
    # страницей ошибки подменять нельзя.
    if exc.headers and "Location" in exc.headers:
        return RedirectResponse(exc.headers["Location"], status_code=exc.status_code)
    if not _wants_html(request):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return _trouble(request, exc.status_code, str(exc.detail or ""))


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    # Полная трасса — в журнал службы (journalctl -u str-1-app), гостю только
    # человеческая формулировка: подробности ошибки ему всё равно не помогут.
    log.exception("необработанная ошибка на %s", request.url.path)
    if not _wants_html(request):
        return JSONResponse({"detail": "внутренняя ошибка"}, status_code=500)
    return _trouble(request, 500)
