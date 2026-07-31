"""Дегустации, справочник виски и назначение номеров образцов."""

import pytest

from app import models


def _whisky(name, wclass="односолодовый скотч", region="Speyside"):
    return models.save_whisky({"name": name, "wclass": wclass, "region": region})


def test_create_tasting_and_defaults():
    tasting_id = models.create_tasting("Тестовая", "2026-08-08", "class")
    tasting = models.get_tasting(tasting_id)
    assert tasting["title"] == "Тестовая"
    assert tasting["status"] == "draft"
    assert tasting["category_level"] == "class"


def test_whisky_numeric_fields_are_parsed():
    whisky_id = models.save_whisky({"name": "Aberlour 13", "abv": "40,0", "age_years": "13"})
    whisky = models.get_whisky(whisky_id)
    # Запятая как разделитель — то, что реально набирают на телефоне.
    assert whisky["abv"] == 40.0
    assert whisky["age_years"] == 13


def test_whisky_requires_name():
    with pytest.raises(ValueError):
        models.save_whisky({"name": "   "})


def test_whisky_rejects_non_numeric_abv():
    with pytest.raises(ValueError):
        models.save_whisky({"name": "Что-то", "abv": "сорок"})


def test_samples_get_sequential_numbers():
    tasting_id = models.create_tasting("Тестовая", None, "class")
    for name in ("Первый", "Второй", "Третий"):
        models.add_whisky_to_tasting(tasting_id, _whisky(name))
    numbers = [row["sample_no"] for row in models.tasting_whiskies(tasting_id)]
    assert numbers == [1, 2, 3]


def test_same_whisky_cannot_be_added_twice():
    tasting_id = models.create_tasting("Тестовая", None, "class")
    whisky_id = _whisky("Единственный")
    models.add_whisky_to_tasting(tasting_id, whisky_id)
    with pytest.raises(ValueError):
        models.add_whisky_to_tasting(tasting_id, whisky_id)


def test_shuffle_keeps_numbers_unique_and_complete():
    tasting_id = models.create_tasting("Тестовая", None, "class")
    for name in ("A", "B", "C", "D", "E"):
        models.add_whisky_to_tasting(tasting_id, _whisky(name))
    models.shuffle_samples(tasting_id)
    numbers = sorted(row["sample_no"] for row in models.tasting_whiskies(tasting_id))
    assert numbers == [1, 2, 3, 4, 5]


def test_removing_a_sample_closes_the_gap():
    tasting_id = models.create_tasting("Тестовая", None, "class")
    ids = [_whisky(name) for name in ("A", "B", "C")]
    for whisky_id in ids:
        models.add_whisky_to_tasting(tasting_id, whisky_id)
    models.remove_whisky_from_tasting(tasting_id, ids[0])
    numbers = sorted(row["sample_no"] for row in models.tasting_whiskies(tasting_id))
    assert numbers == [1, 2], "после удаления номера должны остаться подряд"


def test_status_moves_only_along_allowed_path():
    tasting_id = models.create_tasting("Тестовая", None, "class")
    with pytest.raises(ValueError):
        # Нельзя перепрыгнуть регистрацию и сразу открыть раунд.
        models.set_status(tasting_id, "round_nose")
    models.set_status(tasting_id, "registration")
    models.set_status(tasting_id, "round_nose")
    assert models.get_tasting(tasting_id)["status"] == "round_nose"


def test_composition_is_frozen_after_rounds_start():
    tasting_id = models.create_tasting("Тестовая", None, "class")
    models.add_whisky_to_tasting(tasting_id, _whisky("A"))
    models.set_status(tasting_id, "registration")
    models.set_status(tasting_id, "round_nose")
    with pytest.raises(ValueError):
        models.shuffle_samples(tasting_id)
    with pytest.raises(ValueError):
        models.add_whisky_to_tasting(tasting_id, _whisky("B"))
