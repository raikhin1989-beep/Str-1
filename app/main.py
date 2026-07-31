"""Точка входа приложения дегустации виски.

Слушает 127.0.0.1:8082 и наружу не торчит: снаружи всё приходит через Caddy,
который отдаёт /healthz, /version и /static сам файлами, а остальное проксирует
сюда. Разделение описано в docs/ARCHITECTURE.md.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

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


@app.get("/api/health")
def health() -> dict[str, str]:
    """Живо ли приложение.

    Отдельно от /healthz: тот отдаётся файлом и проверяет, что доехал деплой.
    Этот отвечает, только если работает сам процесс приложения.
    """
    return {"status": "ok"}


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
