"""Выбор провайдера распознавания и разбор ответа Яндекса."""

import json
import time

import pytest

from app import ai
from app.config import ai_provider


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "YANDEX_API_KEY", "YANDEX_FOLDER_ID", "AI_PROVIDER", "AI_PHOTO"):
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


def test_yandex_hides_photo_until_it_is_allowed(client, monkeypatch):
    """У Яндекса фото упирается в права, а не в код: пока их нет, кнопки нет."""
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    assert ai.supports_images() is False
    page = client.get("/whisky", params={"q": "нет такого"}).text
    assert "Спросить у ИИ" in page
    assert "Сфотографируйте этикетку" not in page

    monkeypatch.setenv("AI_PHOTO", "on")
    assert ai.supports_images() is True
    assert "Сфотографируйте этикетку" in client.get("/whisky", params={"q": "нет такого"}).text


def test_photo_appears_by_itself_once_ocr_answers(client, monkeypatch):
    """Ради этого проверка и делается: права выдали в чужой консоли, а кнопка
    появилась сама — без секрета, без выката и без нашего участия."""
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    assert "Сфотографируйте этикетку" not in client.get("/whisky", params={"q": "х"}).text

    monkeypatch.setattr(ai, "_ask_ocr_whether_we_may", lambda: True)
    ai._probe_ocr()
    assert ai.supports_images() is True
    assert "Сфотографируйте этикетку" in client.get("/whisky", params={"q": "х"}).text


def test_the_switch_beats_the_probe_both_ways(monkeypatch):
    """Иногда нужно увидеть настоящую ошибку, а иногда — спрятать рабочую кнопку."""
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")

    monkeypatch.setenv("AI_PHOTO", "on")
    assert ai.supports_images() is True, "включено вручную вопреки отказу OCR"

    monkeypatch.setattr(ai, "_ask_ocr_whether_we_may", lambda: True)
    ai._probe_ocr()
    monkeypatch.setenv("AI_PHOTO", "off")
    assert ai.supports_images() is False, "выключено вручную вопреки разрешению"


def test_asking_ocr_never_delays_the_page(monkeypatch):
    """Проверка уходит в фон. /api/health однажды уже вис на подобном вопросе,
    заданном по дороге, — этого больше не должно случиться."""
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")

    def sleeping() -> bool:
        time.sleep(3)
        return True

    monkeypatch.setattr(ai, "_ask_ocr_whether_we_may", sleeping)
    started = time.monotonic()
    assert ai.ocr_allowed() is False, "пока ответа нет, кнопки нет"
    assert time.monotonic() - started < 0.5, "ответ должен быть мгновенным"


def test_a_refusal_is_rechecked_sooner_than_a_permission(monkeypatch):
    """Роль выдают в консоли, и кнопка должна появиться сама — значит отказ
    протухает быстро. Разрешение перепроверять так же часто незачем."""
    assert ai.OCR_PROBE_FAIL_SECONDS < ai.OCR_PROBE_OK_SECONDS


def test_without_a_yandex_key_nobody_is_asked(monkeypatch):
    """Спрашивать OCR не о чем и нечем: запроса быть не должно."""
    monkeypatch.delenv("YANDEX_API_KEY", raising=False)

    def explode() -> bool:
        raise AssertionError("к OCR постучались без ключа")

    monkeypatch.setattr(ai, "_ask_ocr_whether_we_may", explode)
    assert ai.ocr_allowed() is False


def test_anthropic_takes_photos_without_a_switch(monkeypatch):
    """Там картинку понимает сама модель — включать нечего."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ключ")
    assert ai.supports_images() is True


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


def test_a_model_that_did_not_see_the_photo_is_not_an_answer(monkeypatch, no_ocr):
    """«Фото не прикреплено» — это слепая модель, а не результат распознавания."""
    answers = {
        "aliceai-llm": '{"recognized": false, "comment": "Фотография не прикреплена"}',
        "aliceai-llm-flash": '{"recognized": true, "name": "Laphroaig 10"}',
    }

    def fake_post(payload, allow_retry):
        model = payload["model"].split("/")[3]
        return {"choices": [{"message": {"content": answers[model]}}]}

    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(ai, "_yandex_post", fake_post)
    monkeypatch.setattr(ai, "_yandex_models", lambda: list(answers))

    card = ai._ask_yandex("что на фото?", image=(b"\xff\xd8data", "image/jpeg"))
    assert card["name"] == "Laphroaig 10"
    assert "картинку не увидела" in card["via"]


def test_ocr_forbidden_names_the_role_to_grant(monkeypatch):
    """403 у OCR чинится одной ролью в консоли — об этом и надо сказать."""
    def refuse_ocr(image):
        raise ai.AiUnavailable("403. Permission denied")

    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(ai, "_yandex_ocr", refuse_ocr)
    monkeypatch.setattr(ai, "_yandex_models", lambda: ["yandexgpt"])

    with pytest.raises(ai.AiUnavailable) as err:
        ai._ask_yandex("что на фото?", image=(b"\xff\xd8data", "image/jpeg"))
    assert "ai.vision.user" in str(err.value)


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


# Настоящая проверка прав, пойманная до того, как conftest подменит её заглушкой.
ASK_OCR = ai._ask_ocr_whether_we_may


@pytest.mark.parametrize(
    "status, allowed",
    [
        (200, True),    # прочитал (на картинке 1×1 читать нечего — это нормально)
        (400, True),    # запрос не понравился, но до нас дошли и пустили
        (401, False),   # ключ не тот
        (403, False),   # роли или области действия нет
        (500, False),   # сервису плохо — обещать гостю нечего
    ],
)
def test_ocr_permission_is_read_from_the_status(monkeypatch, status, allowed):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr("httpx.post", lambda *a, **kw: _Response(status, {}))
    assert ASK_OCR() is allowed


def test_a_network_failure_is_not_taken_as_permission(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")

    def boom(*a, **kw):
        raise OSError("сеть недоступна")

    monkeypatch.setattr("httpx.post", boom)
    assert ASK_OCR() is False


def test_the_probe_sends_a_real_jpeg(monkeypatch):
    """Смысл целой картинки вместо мусора: на битом теле сервис может ответить
    400 ещё до проверки ключа, и «400» перестало бы значить «нам можно»."""
    import base64
    import struct

    raw = base64.b64decode(ai.OCR_PROBE_JPEG)
    assert raw[:2] == b"\xff\xd8" and raw[-2:] == b"\xff\xd9"
    start = raw.find(b"\xff\xc0")
    height, width = struct.unpack(">HH", raw[start + 5 : start + 9])
    assert (width, height) == (1, 1), "картинка должна быть крошечной: её шлют часто"

    sent = {}
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gtest")
    monkeypatch.setattr(
        "httpx.post",
        lambda url, **kw: sent.update(url=url, json=kw["json"]) or _Response(200, {}),
    )
    ASK_OCR()
    assert sent["url"] == ai.YANDEX_OCR_URL
    assert sent["json"]["mimeType"] == "JPEG"
    assert sent["json"]["content"] == ai.OCR_PROBE_JPEG
