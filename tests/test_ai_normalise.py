"""Причёсывание ответа модели.

Все случаи ниже — не выдумка: ровно так ответил Яндекс на первый живой запрос
про Laphroaig 10. Тесты с идеальной карточкой этого поймать не могли.
"""

import pytest

from app import ai, models


def test_percent_sign_is_stripped_from_abv():
    # Пришло «40%», шаблон дописывал « %» — на странице выходило «40% %».
    assert ai.normalise_card({"abv": "40%"})["abv"] == "40"


def test_units_are_stripped_from_age_and_price():
    card = ai.normalise_card({"age_years": "10 лет", "price_rub": "около 8000 ₽"})
    assert card["age_years"] == "10"
    assert card["price_rub"] == "8000"


def test_comma_decimal_becomes_dot():
    assert ai.normalise_card({"abv": "41,5 %"})["abv"] == "41.5"


def test_field_without_digits_becomes_empty():
    assert ai.normalise_card({"abv": "не указано"})["abv"] == ""


def test_english_class_maps_to_ours():
    """По классу считаются частичные баллы, «Single Malt» их бы сломал."""
    assert ai.normalise_card({"wclass": "Single Malt"})["wclass"] == "односолодовый скотч"
    assert ai.normalise_card({"wclass": "Blended Scotch"})["wclass"] == "купажированный скотч"
    assert ai.normalise_card({"wclass": "Rye whiskey"})["wclass"] == "ржаной"


def test_known_class_survives_untouched():
    assert ai.normalise_card({"wclass": "бурбон"})["wclass"] == "бурбон"


def test_unknown_class_is_left_as_is_for_the_admin_to_fix():
    assert ai.normalise_card({"wclass": "нечто своё"})["wclass"] == "нечто своё"


def test_confidence_is_lowercased_or_dropped():
    assert ai.normalise_card({"confidence": "Высокая"})["confidence"] == "высокая"
    assert ai.normalise_card({"confidence": "не знаю"})["confidence"] == ""


def test_normalised_card_can_be_saved_to_the_catalogue():
    """Главное: после причёсывания карточка сохраняется, а не падает на числах."""
    raw = {
        "name": "Laphroaig 10", "wclass": "Single Malt", "region": "Islay",
        "abv": "40%", "age_years": "10 лет", "price_rub": "8000 ₽",
    }
    whisky_id = models.save_whisky(ai.normalise_card(raw), source="ai")
    saved = models.get_whisky(whisky_id)
    assert saved["abv"] == 40.0
    assert saved["age_years"] == 10
    assert saved["price_rub"] == 8000
    assert saved["wclass"] == "односолодовый скотч"


def test_raw_card_would_have_failed_to_save():
    """Тот же ответ без причёсывания — ошибка, которую увидел бы админ."""
    with pytest.raises(ValueError):
        models.save_whisky({"name": "Laphroaig 10", "abv": "40%"})


def test_cache_is_tidied_on_read(monkeypatch):
    """В кэше лежат ответы, записанные до причёсывания, — чинить их на чтении."""
    monkeypatch.setenv("YANDEX_API_KEY", "ключ")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    ai._to_cache("name:старая запись", "text", {"name": "Laphroaig 10", "abv": "40%"})
    assert ai._from_cache("name:старая запись")["abv"] == "40"


def test_recognized_as_string_false_is_really_false():
    """Модель прислала строку "false"; в шаблоне она истинна — страница ломалась."""
    card = ai.normalise_card({"recognized": "false", "name": "Гыгыгы Особая"})
    assert card["recognized"] is False


def test_recognized_without_a_name_is_false():
    """«Узнал», но название пустое — на странице выходил пустой заголовок."""
    assert ai.normalise_card({"recognized": True, "name": ""})["recognized"] is False
    assert ai.normalise_card({"recognized": "true", "name": "  "})["recognized"] is False


def test_recognized_stays_true_when_there_is_a_name():
    assert ai.normalise_card({"recognized": "true", "name": "Laphroaig 10"})["recognized"] is True
    assert ai.normalise_card({"recognized": True, "name": "Laphroaig 10"})["recognized"] is True
