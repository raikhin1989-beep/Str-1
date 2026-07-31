"""Публичные страницы: поиск виски по справочнику и карточка.

Здесь намеренно нет ничего про дегустации: номера образцов — единственное, что
скрывает от участников содержимое стаканов, поэтому публичные страницы вообще
не знают о связи виски с дегустацией.
"""

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates

from app import ai, auth, models

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

router = APIRouter()


@router.get("/whisky")
def whisky_search(request: Request, q: str = ""):
    found = models.search_whiskies(q)
    return templates.TemplateResponse(
        request,
        "whisky_search.html",
        {
            "query": q,
            "found": found,
            "searched": bool(q.strip()),
            "ai_available": ai.is_configured(),
            "photo_available": ai.supports_images(),
        },
    )


def _ai_card(request: Request, card: dict, cache_key: str, status_code: int = 200):
    """Показать карточку, полученную от модели.

    Кнопка «в справочник» видна только админу: иначе любой прохожий наполнял бы
    справочник, по которому потом считается конкурс.
    """
    return templates.TemplateResponse(
        request,
        "whisky_ai.html",
        {
            "card": card,
            "cache_key": cache_key,
            "is_admin": auth.session_is_valid(request.cookies.get(auth.COOKIE_NAME)),
        },
        status_code=status_code,
    )


def _ai_error(request: Request, message: str, status_code: int):
    return templates.TemplateResponse(
        request, "whisky_ai_error.html", {"message": message}, status_code=status_code
    )


@router.post("/whisky/ask")
def whisky_ask(request: Request, q: str = Form("")):
    query = q.strip()
    if not query:
        return _ai_error(request, "Введите название виски.", 400)
    try:
        ai.check_rate_limit(auth.client_ip(request))
        card = ai.lookup_by_name(query)
    except ai.RateLimited:
        return _ai_error(request, "Слишком много запросов подряд. Попробуйте через час.", 429)
    except ai.AiUnavailable as err:
        return _ai_error(request, str(err), 503)
    return _ai_card(request, card, ai.cache_key_for_name(query))


@router.post("/whisky/photo")
async def whisky_photo(request: Request, photo: UploadFile = File(...)):
    # Читаем с запасом в один байт: так превышение лимита видно сразу,
    # а не после того, как файл целиком окажется в памяти.
    data = await photo.read(ai.MAX_IMAGE_BYTES + 1)
    if not data:
        return _ai_error(request, "Файл пустой — выберите фотографию.", 400)
    try:
        ai.check_rate_limit(auth.client_ip(request))
        card = ai.lookup_by_photo(data, photo.content_type or "")
    except ai.RateLimited:
        return _ai_error(request, "Слишком много запросов подряд. Попробуйте через час.", 429)
    except ai.AiUnavailable as err:
        return _ai_error(request, str(err), 503)
    return _ai_card(request, card, ai.cache_key_for_image(data))


@router.get("/whisky/{whisky_id}")
def whisky_card(request: Request, whisky_id: int):
    whisky = models.get_whisky(whisky_id)
    if whisky is None:
        raise HTTPException(status_code=404, detail="Виски не найден")
    return templates.TemplateResponse(request, "whisky_card.html", {"whisky": whisky})
