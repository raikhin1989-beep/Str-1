"""Публичный поиск виски и карточка."""

from app import models


def _fill_catalogue():
    models.save_whisky(
        {"name": "Aberlour 13 Double Cask", "wclass": "односолодовый скотч",
         "region": "Speyside", "abv": "40", "nose": "мёд и сухофрукты"}
    )
    models.save_whisky(
        {"name": "Аберлауэр 16", "wclass": "односолодовый скотч", "region": "Speyside"}
    )
    models.save_whisky(
        {"name": "Jack Daniel's Single Barrel Rye", "wclass": "ржаной", "region": "Tennessee"}
    )


def test_search_page_lists_catalogue_without_query(client):
    _fill_catalogue()
    response = client.get("/whisky")
    assert response.status_code == 200
    assert "Aberlour 13 Double Cask" in response.text
    assert "Jack Daniel&#39;s Single Barrel Rye" in response.text


def test_search_finds_by_partial_latin_name(client):
    _fill_catalogue()
    response = client.get("/whisky", params={"q": "aberlour"})
    assert "Aberlour 13 Double Cask" in response.text
    assert "Jack Daniel" not in response.text


def test_search_is_case_insensitive_for_cyrillic(client):
    # LIKE в SQLite для кириллицы регистр не игнорирует — поэтому фильтруем
    # в Python. Тест держит это поведение.
    _fill_catalogue()
    response = client.get("/whisky", params={"q": "аберлауэр"})
    assert "Аберлауэр 16" in response.text


def test_search_finds_by_region(client):
    _fill_catalogue()
    response = client.get("/whisky", params={"q": "tennessee"})
    assert "Jack Daniel" in response.text
    assert "Aberlour 13" not in response.text


def test_search_without_matches_offers_photo(client):
    _fill_catalogue()
    response = client.get("/whisky", params={"q": "такого нет"})
    assert response.status_code == 200
    assert "ничего не нашлось" in response.text
    assert "фотографии" in response.text


def test_card_shows_filled_fields_only(client):
    _fill_catalogue()
    whisky_id = models.search_whiskies("Aberlour 13")[0]["id"]
    response = client.get(f"/whisky/{whisky_id}")
    assert response.status_code == 200
    assert "мёд и сухофрукты" in response.text
    assert "Крепость" in response.text
    # Незаполненные поля не показываем пустыми строками.
    assert "Бочка" not in response.text


def test_unknown_card_gives_404(client):
    assert client.get("/whisky/999").status_code == 404


def test_public_pages_never_reveal_tasting_or_sample_numbers(client):
    """Главная тайна конкурса — какой номер какому виски соответствует.

    Публичные страницы не должны знать о связи виски с дегустацией вообще.
    """
    _fill_catalogue()
    whisky_id = models.search_whiskies("Aberlour 13")[0]["id"]
    tasting_id = models.create_tasting("СЕКРЕТНАЯ ДЕГУСТАЦИЯ", None, "class")
    models.add_whisky_to_tasting(tasting_id, whisky_id)

    for url in ("/whisky", f"/whisky/{whisky_id}"):
        text = client.get(url).text
        assert "СЕКРЕТНАЯ ДЕГУСТАЦИЯ" not in text
        assert "образец" not in text.lower()


def test_index_links_to_search(client):
    assert '/whisky' in client.get("/").text
