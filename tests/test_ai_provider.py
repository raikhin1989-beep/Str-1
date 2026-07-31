"""Выбор провайдера распознавания и разбор ответа Яндекса."""

import json

import pytest

from app import ai
from app.config import ai_provider


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "YANDEX_API_KEY", "YANDEX_FOLDER_ID", "AI_PROVIDER"):
        monkeypatch.delenv(name, raising=False)


def test_no_keys_means_no_provider():
    assert ai_provider() is None
    assert ai.is_configured() is False


def test_anthropic_alone(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ключ")
    assert ai_provider() == "anthropic"
    assert ai.supports_images() is True


def test_yandex_needs_both_key_and_folder(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    assert ai_provider() is None, "без каталога ключ Яндекса бесполезен"
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    assert ai_provider() == "yandex"


def test_yandex_wins_over_anthropic(monkeypatch):
    """Сервер в России: Anthropic отсюда недоступен, значит Яндекс важнее."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    assert ai_provider() == "yandex"


def test_provider_can_be_forced(monkeypatch):
    """После переезда хостинга переключаемся переменной, а не выпиливанием ключей."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    assert ai_provider() == "anthropic"
    monkeypatch.setenv("AI_PROVIDER", "off")
    assert ai_provider() is None


def test_photo_is_hidden_while_yandex_answers(client, monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    assert ai.supports_images() is False
    page = client.get("/whisky", params={"q": "нет такого"}).text
    assert "Спросить у ИИ" in page, "поиск по названию Яндекс умеет"
    assert "Сфотографируйте этикетку" not in page, "а кнопки фото быть не должно"


def test_photo_request_is_refused_politely(client, monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    response = client.post(
        "/whisky/photo", files={"photo": ("p.jpg", b"\xff\xd8data", "image/jpeg")}
    )
    assert response.status_code == 503
    assert "недоступно" in response.text


CARD_JSON = {
    "recognized": True, "name": "Laphroaig 10", "distillery": "Laphroaig",
    "wclass": "односолодовый скотч", "region": "Islay", "abv": "40",
    "age_years": "10", "cask": "ex-bourbon", "grain": "ячменный солод",
    "filtration": "да", "price_rub": "6000", "colour": "золото",
    "nose": "торф и йод", "palate": "дым и морская соль", "finish": "долгое",
    "confidence": "высокая", "comment": "",
}


def test_parse_card_tolerates_markdown_fences():
    text = "Вот карточка:\n```json\n" + json.dumps(CARD_JSON, ensure_ascii=False) + "\n```"
    assert ai._parse_card(text)["name"] == "Laphroaig 10"


def test_parse_card_fills_missing_fields():
    """Не всякая модель держит схему дословно — недостающее не должно ронять страницу."""
    card = ai._parse_card('{"name": "Что-то", "nose": "дым"}')
    assert card["recognized"] is True
    assert card["palate"] == ""
    assert set(ai.CARD_SCHEMA["required"]) <= set(card)


def test_parse_card_rejects_gibberish():
    with pytest.raises(ai.AiUnavailable):
        ai._parse_card("извините, не понял")
