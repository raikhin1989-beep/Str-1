"""Точка входа приложения дегустации виски.

Слушает 127.0.0.1:8082 и наружу не торчит: снаружи всё приходит через Caddy,
который отдаёт /healthz, /version и /static сам файлами, а остальное проксирует
сюда. Разделение описано в docs/ARCHITECTURE.md.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from app import ai
from app.admin import router as admin_router
from app.config import admin_password
from app.public import router as public_router

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
    }


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
