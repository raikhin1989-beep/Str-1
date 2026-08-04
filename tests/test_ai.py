"""Распознавание виски: кэш, ограничение частоты, обработка отказов.

Обращение к API подменяется: тесты не ходят в сеть и ничего не стоят.
"""

import pytest

from app import ai
from tests.conftest import TEST_PASSWORD

CARD = {
    "recognized": True,
    "name": "Aberlour 13 Double Cask Matured",
    "distillery": "Aberlour",
    "wclass": "односолодовый скотч",
    "region": "Speyside",
    "abv": "40",
    "age_years": "13",
    "cask": "американский дуб, олоросо",
    "grain": "ячменный солод",
    "filtration": "неизвестно",
    "price_rub": "6500",
    "colour": "тёмное золото",
    "nose": "мёд, яблоко, сухофрукты",
    "palate": "изюм и специи",
    "finish": "долгое, тёплое",
    "confidence": "средняя",
    "comment": "",
}


@pytest.fixture
def fake_model(monkeypatch):
    """Подменяет единственное место, где происходит обращение к API."""
    calls = []

    def _ask(prompt, image=None):
        calls.append((prompt, image))
        return CARD

    monkeypatch.setattr(ai, "_ask", _ask)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "тестовый-ключ")
    monkeypatch.delenv("YANDEX_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    ai._requests.clear()
    return calls


def test_lookup_by_name_returns_card(fake_model):
    card = ai.lookup_by_name("Aberlour 13")
    assert card["name"] == "Aberlour 13 Double Cask Matured"
    assert len(fake_model) == 1


def test_repeated_lookup_comes_from_cache(fake_model):
    ai.lookup_by_name("Aberlour 13")
    ai.lookup_by_name("  aberlour   13  ")  # тот же запрос с другим написанием
    assert len(fake_model) == 1, "второй запрос должен был взяться из кэша"


def test_photo_is_cached_by_content(fake_model):
    ai.lookup_by_photo(b"\xff\xd8picture", "image/jpeg")
    ai.lookup_by_photo(b"\xff\xd8picture", "image/jpeg")
    assert len(fake_model) == 1


def test_a_failure_is_not_remembered(monkeypatch, fake_model):
    """Пойманное на живом сайте: фотографию принесли, когда прав на чтение
    этикетки не было, отказ осел в кэше — и после починки прав та же самая
    фотография продолжала получать старый ответ мимо модели."""
    failure = dict(CARD, recognized=False, comment="Фотография не приложена.")
    monkeypatch.setattr(ai, "_ask", lambda prompt, image=None: failure)
    assert ai.lookup_by_photo(b"\xff\xd8bottle", "image/jpeg")["recognized"] is False

    # Права починили — та же фотография должна дойти до модели, а не до кэша.
    monkeypatch.setattr(ai, "_ask", lambda prompt, image=None: CARD)
    assert ai.lookup_by_photo(b"\xff\xd8bottle", "image/jpeg")["recognized"] is True


def test_a_failed_name_lookup_is_not_remembered_either(monkeypatch, fake_model):
    failure = dict(CARD, recognized=False, comment="Не понял, о чём речь.")
    monkeypatch.setattr(ai, "_ask", lambda prompt, image=None: failure)
    ai.lookup_by_name("что-то невнятное")

    seen = []
    monkeypatch.setattr(ai, "_ask", lambda prompt, image=None: seen.append(prompt) or CARD)
    ai.lookup_by_name("что-то невнятное")
    assert seen, "повтор должен был дойти до модели"


def test_photo_rejects_wrong_format(fake_model):
    with pytest.raises(ai.AiUnavailable):
        ai.lookup_by_photo(b"data", "application/pdf")


def test_photo_rejects_oversized_file(fake_model):
    with pytest.raises(ai.AiUnavailable):
        ai.lookup_by_photo(b"x" * (ai.MAX_IMAGE_BYTES + 1), "image/jpeg")


def test_rate_limit_trips_after_the_quota(fake_model):
    for _ in range(ai.RATE_LIMIT):
        ai.check_rate_limit("10.0.0.1")
    with pytest.raises(ai.RateLimited):
        ai.check_rate_limit("10.0.0.1")
    # Другой адрес не задет.
    ai.check_rate_limit("10.0.0.2")


def test_without_key_the_feature_is_off(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("YANDEX_API_KEY", raising=False)
    assert ai.is_configured() is False
    # Кнопки распознавания на странице поиска нет.
    assert "Спросить у ИИ" not in client.get("/whisky", params={"q": "нет такого"}).text
    # А прямой запрос отвечает понятным сообщением, а не пятисоткой.
    response = client.post("/whisky/ask", data={"q": "Aberlour"})
    assert response.status_code == 503
    assert "не заданы ключи" in response.text


def test_ask_shows_card(client, fake_model):
    response = client.post("/whisky/ask", data={"q": "Aberlour 13"})
    assert response.status_code == 200
    assert "мёд, яблоко, сухофрукты" in response.text
    assert "ориентировочные" in response.text


def test_unrecognized_photo_explains_itself(client, monkeypatch, fake_model):
    monkeypatch.setattr(
        ai, "_ask",
        lambda prompt, image=None: {**CARD, "recognized": False, "comment": "На фото не видно этикетки."},
    )
    response = client.post(
        "/whisky/photo", files={"photo": ("p.jpg", b"\xff\xd8data", "image/jpeg")}
    )
    assert response.status_code == 200
    assert "На фото не видно этикетки." in response.text
    assert "Крепость" not in response.text


def test_import_button_hidden_from_guests(client, fake_model):
    assert "Добавить в справочник" not in client.post(
        "/whisky/ask", data={"q": "Aberlour 13"}
    ).text


def test_admin_can_import_card_into_catalogue(client, fake_model):
    client.post("/admin/login", data={"password": TEST_PASSWORD})
    page = client.post("/whisky/ask", data={"q": "Aberlour 13"})
    assert "Добавить в справочник" in page.text

    response = client.post(
        "/admin/whiskies/import",
        data={"cache_key": ai.cache_key_for_name("Aberlour 13")},
        follow_redirects=True,
    )
    assert response.status_code == 200
    from app import models
    # Ищем по точному названию из карточки: в справочнике уже лежит похожая
    # запись из сидовой миграции, «Aberlour 13 Year Old Double Cask Matured».
    saved = [w for w in models.list_whiskies() if w["name"] == CARD["name"]]
    assert len(saved) == 1
    assert saved[0]["source"] == "ai", "карточка от модели должна быть помечена как ориентировочная"
    assert saved[0]["abv"] == 40.0


def test_import_with_unknown_key_is_refused(client, fake_model):
    client.post("/admin/login", data={"password": TEST_PASSWORD})
    response = client.post(
        "/admin/whiskies/import", data={"cache_key": "name:такого нет"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "error" in response.headers["location"]


def test_guest_cannot_import(client, fake_model):
    ai.lookup_by_name("Aberlour 13")
    response = client.post(
        "/admin/whiskies/import",
        data={"cache_key": ai.cache_key_for_name("Aberlour 13")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_import_returns_to_the_search_page(admin, fake_model):
    """Карточку распознают из поиска — туда и возвращаемся, а не в форму правки."""
    ai.lookup_by_name("Aberlour 13")
    response = admin.post(
        "/admin/whiskies/import",
        data={"cache_key": ai.cache_key_for_name("Aberlour 13")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/whisky?q=")
    assert "added=" in location

    page = admin.get(location).text
    assert "добавлен в справочник" in page
    assert CARD["name"] in page
    assert "Проверить поля" in page, "правка на месте, просто одним щелчком"


def test_a_guest_on_that_page_sees_no_admin_link(admin, fake_model):
    """Отдельный клиент: фикстура admin — это тот же браузер с куки входа."""
    from fastapi.testclient import TestClient

    from app.main import app

    ai.lookup_by_name("Aberlour 13")
    location = admin.post(
        "/admin/whiskies/import",
        data={"cache_key": ai.cache_key_for_name("Aberlour 13")},
        follow_redirects=False,
    ).headers["location"]

    with TestClient(app) as guest:
        page = guest.get(location).text
    assert "добавлен в справочник" in page
    assert "Проверить поля" not in page
