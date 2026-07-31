"""Выбор провайдера распознавания и разбор ответа Яндекса."""

import json

import pytest

from app import ai
from app.config import ai_provider


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "YANDEX_API_KEY", "YANDEX_FOLDER_ID", "AI_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    ai.reset_models_cache()


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


def test_yandex_offers_photo_too(client, monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    assert ai.supports_images() is True
    page = client.get("/whisky", params={"q": "нет такого"}).text
    assert "Спросить у ИИ" in page
    assert "Сфотографируйте этикетку" in page


@pytest.fixture
def no_ocr(monkeypatch):
    """Этикетка не прочиталась — значит, дело дойдёт до показа самой фотографии."""
    monkeypatch.setattr(ai, "_yandex_ocr", lambda image: "")


def test_label_is_read_by_ocr_first(monkeypatch):
    """Название и крепость на этикетке написаны буквами — читать их надёжнее, чем угадывать."""
    seen = {}

    def fake_post(payload, allow_retry):
        seen["model"] = payload["model"]
        seen["prompt"] = payload["messages"][-1]["content"][0]["text"]
        return {"choices": [{"message": {"content": '{"name": "Laphroaig 10"}'}}]}

    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(ai, "_yandex_post", fake_post)
    monkeypatch.setattr(ai, "_yandex_ocr", lambda image: "LAPHROAIG 10 YEARS OLD 40%")

    card = ai._ask_yandex("что на фото?", image=(b"\xff\xd8data", "image/jpeg"))
    assert card["name"] == "Laphroaig 10"
    assert "OCR" in card["via"]
    # Текстовой модели, а не картиночной: картинку она всё равно не увидит.
    assert seen["model"] == "gpt://b1gtest/yandexgpt/latest"
    assert "LAPHROAIG 10 YEARS OLD 40%" in seen["prompt"]


def test_ocr_reads_the_full_text_of_a_page(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(
        "httpx.post",
        lambda *a, **kw: _Response(
            200, {"result": {"textAnnotation": {"fullText": "LAPHROAIG\n10 YEARS"}}}
        ),
    )
    assert ai._yandex_ocr((b"\xff\xd8data", "image/jpeg")) == "LAPHROAIG 10 YEARS"


def test_ocr_skips_formats_it_cannot_take(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr("httpx.post", lambda *a, **kw: pytest.fail("WebP слать не надо"))
    assert ai._yandex_ocr((b"RIFF", "image/webp")) == ""


def test_photo_goes_to_a_vision_model(monkeypatch, no_ocr):
    """Текст и картинку обслуживают разные модели, и картиночную выбираем из открытых."""
    seen = {}

    def fake_post(payload, allow_retry):
        seen["model"] = payload["model"]
        seen["content"] = payload["messages"][-1]["content"]
        return {"choices": [{"message": {"content": '{"name": "Laphroaig 10"}'}}]}

    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(ai, "_yandex_post", fake_post)
    monkeypatch.setattr(ai, "_yandex_models", lambda: ["yandexgpt", "aliceai-llm"])

    ai._ask_yandex("что это?")
    assert seen["model"] == "gpt://b1gtest/yandexgpt/latest"

    ai._ask_yandex("что на фото?", image=(b"\xff\xd8data", "image/jpeg"))
    # gemma каталогу не открыта, поэтому берётся следующий кандидат из списка.
    assert seen["model"] == "gpt://b1gtest/aliceai-llm/latest"
    kinds = [part["type"] for part in seen["content"]]
    assert kinds == ["text", "image_url"]
    assert seen["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_next_model_is_tried_when_one_refuses_the_photo(monkeypatch, no_ocr):
    tried = []

    def fake_post(payload, allow_retry):
        model = payload["model"].split("/")[3]
        tried.append(model)
        if model == "gemma-3-27b-it":
            raise ai.AiUnavailable("Яндекс ответил 403. Forbidden")
        return {"choices": [{"message": {"content": '{"name": "Laphroaig 10"}'}}]}

    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(ai, "_yandex_post", fake_post)
    monkeypatch.setattr(ai, "_yandex_models", lambda: ["gemma-3-27b-it", "aliceai-llm"])

    card = ai._ask_yandex("что на фото?", image=(b"\xff\xd8data", "image/jpeg"))
    assert card["name"] == "Laphroaig 10"
    assert tried == ["gemma-3-27b-it", "aliceai-llm"]


def test_all_models_refusing_gives_one_message_with_every_reason(monkeypatch, no_ocr):
    def fake_post(payload, allow_retry):
        raise ai.AiUnavailable("Яндекс ответил 403. Forbidden")

    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(ai, "_yandex_post", fake_post)
    monkeypatch.setattr(ai, "_yandex_models", lambda: ["gemma-3-27b-it", "aliceai-llm"])

    with pytest.raises(ai.AiUnavailable) as err:
        ai._ask_yandex("что на фото?", image=(b"\xff\xd8data", "image/jpeg"))
    assert "gemma-3-27b-it" in str(err.value)
    assert "aliceai-llm" in str(err.value)


def test_folder_without_a_single_vision_model_says_so(monkeypatch, no_ocr):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(ai, "_yandex_models", lambda: ["yandexgpt", "text-embeddings"])

    with pytest.raises(ai.AiUnavailable) as err:
        ai._ask_yandex("что на фото?", image=(b"\xff\xd8data", "image/jpeg"))
    assert "не открыта ни одна модель" in str(err.value)


def test_schema_refusal_falls_back_to_a_plain_request(monkeypatch):
    """Если модель не приняла response_format, спрашиваем без схемы, а не падаем."""
    calls = []

    def fake_post(payload, allow_retry):
        calls.append(("response_format" in payload, allow_retry))
        if allow_retry:
            return None  # так _yandex_post сообщает «схему не приняли»
        return {"choices": [{"message": {"content": '{"name": "Laphroaig 10"}'}}]}

    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(ai, "_yandex_post", fake_post)

    assert ai._ask_yandex("что это?")["name"] == "Laphroaig 10"
    assert calls == [(True, True), (False, False)]


class _Response:
    """Минимальный двойник httpx.Response: нужны только эти четыре вещи."""

    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text if payload is None else json.dumps(payload, ensure_ascii=False)

    def json(self):
        if self._payload is None:
            raise ValueError("не JSON")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_yandex_error_text_reaches_the_page(monkeypatch):
    """Без текста ошибки «403» не объясняет ничего: чинится оно по-разному."""
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(
        "httpx.post",
        lambda *a, **kw: _Response(403, {"error": {"message": "model is not available"}}),
    )

    with pytest.raises(ai.AiUnavailable) as err:
        ai._ask_yandex("что это?")
    assert "403" in str(err.value)
    assert "model is not available" in str(err.value)


def test_non_json_error_body_is_shown_as_is(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr("httpx.post", lambda *a, **kw: _Response(502, text="  bad gateway  "))

    with pytest.raises(ai.AiUnavailable) as err:
        ai._ask_yandex("что это?")
    assert "bad gateway" in str(err.value)


def test_refusal_says_whether_the_model_is_open_to_the_folder(monkeypatch):
    """403 без тела не отличает закрытую модель от недостающих прав — список отличает."""
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr("httpx.post", lambda *a, **kw: _Response(403, text="Forbidden"))
    monkeypatch.setattr(ai, "_yandex_models", lambda: ["qwen3-235b-a22b-fp8", "text-embeddings"])

    with pytest.raises(ai.AiUnavailable) as err:
        ai._ask_yandex("что это?")
    assert "yandexgpt" in str(err.value)
    assert "не открыта" in str(err.value)
    assert "qwen3-235b-a22b-fp8" in str(err.value)


def test_model_list_keeps_only_names(monkeypatch):
    """Идентификатор каталога в сообщение на странице попадать не должен."""
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gsecret")
    monkeypatch.setattr(
        "httpx.get",
        lambda *a, **kw: _Response(
            200, {"data": [{"id": "gpt://b1gsecret/yandexgpt/latest"}, {"id": "мусор"}]}
        ),
    )
    assert ai._yandex_models() == ["yandexgpt"]


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
