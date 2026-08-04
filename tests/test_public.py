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


def test_an_empty_query_shows_no_list_at_all(client):
    """Раньше страница открывалась всем справочником — полутора сотнями
    названий, в которых тонула сама форма. Человек приходит сюда
    с конкретной бутылкой в руке, а не листать каталог."""
    _fill_catalogue()
    response = client.get("/whisky")
    assert response.status_code == 200
    assert "Aberlour 13 Double Cask" not in response.text
    assert "Jack Daniel" not in response.text
    # Но спросить по-прежнему есть чем, и это первое, что видно.
    assert "Название виски" in response.text


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


def test_search_without_matches_says_so(client):
    _fill_catalogue()
    response = client.get("/whisky", params={"q": "такого нет"})
    assert response.status_code == 200
    assert "ничего нет" in response.text


def test_search_offers_ai_only_when_key_is_present(client, monkeypatch):
    _fill_catalogue()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert "Спросить у ИИ" not in client.get("/whisky", params={"q": "нет такого"}).text

    monkeypatch.setenv("ANTHROPIC_API_KEY", "тестовый-ключ")
    with_key = client.get("/whisky", params={"q": "нет такого"}).text
    assert "Спросить у ИИ" in with_key
    assert "Этикетка фотографией" in with_key


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


def test_both_ways_to_ask_are_together_at_the_top(client, monkeypatch):
    """Фотография нужна как раз тому, кто названия не знает, — а лежала она
    отдельным блоком под выдачей, куда ещё надо было долистать."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "тестовый-ключ")
    _fill_catalogue()
    page = client.get("/whisky", params={"q": "aberlour"}).text

    by_name = page.index('name="q"')
    by_photo = page.index('type="file"')
    first_result = page.index("Aberlour 13 Double Cask")
    assert by_name < by_photo < first_result, "оба способа спросить — до выдачи"
    # И в одной карточке, а не в двух разных местах страницы.
    block = page[page.index('class="card find"') : first_result]
    assert 'name="q"' in block and 'type="file"' in block


def test_the_photo_field_does_not_force_the_camera(client, monkeypatch):
    """capture открывал сразу камеру: снять этикетку прямо сейчас можно
    не всегда, а из галереи выбрать — почти всегда."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "тестовый-ключ")
    page = client.get("/whisky").text
    assert "capture=" not in page
    assert "галереи" in page


def test_the_photo_form_works_without_javascript(client, monkeypatch):
    """Скрипт только убирает лишнее касание. Кнопка остаётся в разметке:
    вечер не должен зависеть от того, выполнился ли find.js."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "тестовый-ключ")
    page = client.get("/whisky").text
    form = page[page.index('id="byphoto"') : page.index("</form>", page.index('id="byphoto"'))]
    assert 'action="/whisky/photo"' in page
    assert "Распознать" in form, "без JS отправлять форму нечем"
