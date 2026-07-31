"""Справочник, заполненный миграциями под первую дегустацию.

Состав сверен с коробками (фотографии от 31.07.2026), см. docs/TASTING-001.md.
"""

from app import models

EXPECTED = {
    "The Dalmore The Quartet": ("односолодовый скотч", "Highland", 41.5),
    "Johnnie Walker Black Label Triple Cask Edition": ("купажированный скотч", None, 40.0),
    "Jack Daniel's Single Barrel 100 Proof": ("теннесси", "Tennessee", 50.0),
    "Aberlour Suthainn Double Sherry Cask Solera": ("односолодовый скотч", "Speyside", 48.0),
    "Kemlya American Oak": ("односолодовый (не Шотландия)", "Россия", 49.5),
}

# Чего в составе нет: миграция 002 завела их по списку «на словах», коробки
# показали другое. Пока позиция никуда не налита, она должна исчезнуть.
GONE = {
    "Dewar's 12 Year Old",
    "Jack Daniel's Single Barrel Rye",
    "Aberlour 13 Year Old Double Cask Matured",
}


def test_five_bottles_are_seeded():
    names = {row["name"] for row in models.list_whiskies()}
    assert set(EXPECTED) <= names


def test_bottles_that_are_not_on_the_table_are_gone():
    names = {row["name"] for row in models.list_whiskies()}
    assert names & GONE == set()


def test_class_and_region_match_the_lineup():
    # Класс определяет частичные баллы, поэтому важнее прочих полей.
    for row in models.list_whiskies():
        if row["name"] in EXPECTED:
            wclass, region, abv = EXPECTED[row["name"]]
            assert row["wclass"] == wclass
            assert row["region"] == region
            assert row["abv"] == abv


def test_every_class_in_the_lineup_is_one_we_offer():
    """Класс не из списка молча сломал бы и админку, и частичные баллы."""
    for row in models.list_whiskies():
        if row["name"] in EXPECTED:
            assert row["wclass"] in models.WHISKY_CLASSES


def test_every_bottle_has_a_price():
    """Цена — одно из четырёх обещаний карточки, пустой она быть не должна."""
    for row in models.list_whiskies():
        if row["name"] in EXPECTED:
            assert row["price_rub"], f"{row['name']}: цены нет"


def test_the_one_bottle_sold_in_russia_has_the_shop_price():
    """Kemlya нашлась в рознице ровно этим розливом — тут не ориентир, а цена."""
    kemlya = next(r for r in models.list_whiskies() if r["name"] == "Kemlya American Oak")
    assert kemlya["price_rub"] == 17490
    assert "WineStyle" in kemlya["notes"]


def test_seeded_cards_are_marked_as_unverified():
    for row in models.list_whiskies():
        if row["name"] in EXPECTED:
            assert row["source"] == "ai", "незаверенные данные должны быть помечены"


def test_partial_points_pair_up_as_planned():
    """Единственная пара одного класса — два шотландских односолодовых."""
    by_class: dict[str, list[str]] = {}
    for row in models.list_whiskies():
        if row["name"] in EXPECTED:
            by_class.setdefault(row["wclass"], []).append(row["name"])
    assert len(by_class["односолодовый скотч"]) == 2
    assert sorted(len(names) for names in by_class.values()) == [1, 1, 1, 2]


def test_seed_is_visible_in_public_search(client):
    assert "Suthainn" in client.get("/whisky", params={"q": "aberlour"}).text
