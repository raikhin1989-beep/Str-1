"""Публичные страницы: поиск виски по справочнику и карточка.

Здесь намеренно нет ничего про дегустации: номера образцов — единственное, что
скрывает от участников содержимое стаканов, поэтому публичные страницы вообще
не знают о связи виски с дегустацией.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app import models

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

router = APIRouter()


@router.get("/whisky")
def whisky_search(request: Request, q: str = ""):
    found = models.search_whiskies(q)
    return templates.TemplateResponse(
        request,
        "whisky_search.html",
        {"query": q, "found": found, "searched": bool(q.strip())},
    )


@router.get("/whisky/{whisky_id}")
def whisky_card(request: Request, whisky_id: int):
    whisky = models.get_whisky(whisky_id)
    if whisky is None:
        raise HTTPException(status_code=404, detail="Виски не найден")
    return templates.TemplateResponse(request, "whisky_card.html", {"whisky": whisky})
