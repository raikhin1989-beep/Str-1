"""Справочник, заполненный миграцией под первую дегустацию."""

from app import models

EXPECTED = {
    "The Dalmore The Quartet": ("односолодовый скотч", "Highland", 41.5),
    "Dewar's 12 Year Old": ("купажированный скотч", None, 40.0),
    "Johnnie Walker Black Label Triple Cask Edition": ("купажированный скотч", None, 40.0),
    "Jack Daniel's Single Barrel Rye": ("ржаной", "Tennessee", 47.0),
    "Aberlour 13 Year Old Double Cask Matured": ("односолодовый скотч", "Speyside", 40.0),
}


def test_five_bottles_are_seeded():
    names = {row["name"] for row in models.list_whiskies()}
    assert set(EXPECTED) <= names


def test_class_and_region_match_the_lineup():
    # Класс определяет частичные баллы, поэтому важнее прочих полей.
    for row in models.list_whiskies():
        if row["name"] in EXPECTED:
            wclass, region, abv = EXPECTED[row["name"]]
            assert row["wclass"] == wclass
            assert row["region"] == region
            assert row["abv"] == abv


def test_seeded_cards_are_marked_as_unverified():
    for row in models.list_whiskies():
        if row["name"] in EXPECTED:
            assert row["source"] == "ai", "незаверенные данные должны быть помечены"


def test_partial_points_pair_up_as_planned():
    """Два купажа и два односолодовых — те самые пары, где работает частичный балл."""
    by_class: dict[str, list[str]] = {}
    for row in models.list_whiskies():
        if row["name"] in EXPECTED:
            by_class.setdefault(row["wclass"], []).append(row["name"])
    assert len(by_class["купажированный скотч"]) == 2
    assert len(by_class["односолодовый скотч"]) == 2
    assert len(by_class["ржаной"]) == 1


def test_seed_is_visible_in_public_search(client):
    assert "Aberlour 13" in client.get("/whisky", params={"q": "aberlour"}).text
