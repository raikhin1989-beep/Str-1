"""Справочник ходовых виски — миграция 009.

Он нужен не сам по себе: справочник ещё и список вариантов ответа в раунде
(см. docs/SCORING.md). Пока в нём было пять налитых бутылок, конкурс сводился
к перестановке. Поэтому тут проверяется не «данные красивые», а то, от чего
зависит зачёт: карточка заполнена, класс из нашего словаря, имя одно на
бутылку, а помётка «данные ориентировочные» на месте.
"""

from markupsafe import escape

from app import models

# Из чего собран список. Числа с запасом вниз: сюда будут дописывать руками,
# а тест должен ловить пропавшую миграцию, а не спорить о каждой новой бутылке.
MIN_TOTAL = 120
MIN_PER_CLASS = {
    "односолодовый скотч": 40,
    "купажированный скотч": 15,
    "бурбон": 10,
    "ирландский": 5,
    "японский": 5,
}


def test_catalogue_is_big_enough_to_guess_wrong():
    assert len(models.list_whiskies()) >= MIN_TOTAL


def test_every_class_has_enough_bottles_for_a_partial_point():
    """Балл за верный класс имеет смысл, только если в классе есть из чего выбрать."""
    counts: dict[str, int] = {}
    for row in models.list_whiskies():
        counts[row["wclass"]] = counts.get(row["wclass"], 0) + 1
    for wclass, minimum in MIN_PER_CLASS.items():
        assert counts.get(wclass, 0) >= minimum, f"{wclass}: {counts.get(wclass, 0)}"


def test_every_class_is_one_we_offer():
    """Класс не из словаря молча ломает и админку, и частичные баллы."""
    for row in models.list_whiskies():
        assert row["wclass"] in models.WHISKY_CLASSES, row["name"]


def test_every_card_keeps_its_four_promises():
    """Цена, нос, вкус, финиш — то, ради чего страница виски вообще открывается."""
    for row in models.list_whiskies():
        for field in ("price_rub", "colour", "nose", "palate", "finish", "abv"):
            assert row[field], f"{row['name']}: пусто поле {field}"


def test_names_are_unique():
    names = [row["name"] for row in models.list_whiskies()]
    assert len(names) == len(set(names))


def test_generated_cards_are_marked_as_unverified():
    """Данные написаны нами по памяти о стандартных розливах, не сверены с бутылкой."""
    for row in models.list_whiskies():
        assert row["source"] == "ai"
        assert row["notes"], f"{row['name']}: нет пометки о происхождении данных"


def test_catalogue_is_the_answer_pool(client):
    """Ради этого всё и затевалось: выбор ответа идёт из справочника."""
    tasting_id = models.create_tasting("Проверка справочника", None, "class")
    assert len(models.round_choices(tasting_id)) >= MIN_TOTAL


def test_new_bottles_are_searchable(client):
    page = client.get("/whisky", params={"q": "yamazaki"}).text
    assert "Yamazaki" in page


def test_choices_are_grouped_by_class():
    """Сотня названий одним свитком нечитаема — раскладываем по классам."""
    groups = models.grouped_choices(models.list_whiskies())
    labels = [wclass for wclass, _ in groups]
    assert "односолодовый скотч" in labels
    assert "японский" in labels
    # Порядок групп — как в словаре классов, а не по алфавиту.
    order = [c for c in models.WHISKY_CLASSES if c in labels]
    assert labels == order
    # Ни один виски не потерялся по дороге.
    assert sum(len(rows) for _, rows in groups) == len(models.list_whiskies())


def test_a_class_outside_the_dictionary_still_gets_a_group():
    """Заведённый руками класс не должен уронить виски из вариантов ответа."""
    models.save_whisky({"name": "Нечто самобытное", "wclass": "самогон"})
    groups = dict(models.grouped_choices(models.list_whiskies()))
    assert [r["name"] for r in groups["самогон"]] == ["Нечто самобытное"]


def test_a_whisky_without_a_class_falls_into_the_last_group():
    models.save_whisky({"name": "Безымянный класс", "wclass": ""})
    groups = dict(models.grouped_choices(models.list_whiskies()))
    assert "Безымянный класс" in [r["name"] for r in groups["прочее"]]


def test_the_round_page_lists_the_whole_catalogue(client):
    """Страница раунда действительно отдаёт варианты, а не падает на сотне."""
    tasting_id = models.create_tasting("Вечер", None, "class")
    poured = models.list_whiskies()[:3]
    for row in poured:
        models.add_whisky_to_tasting(tasting_id, row["id"])
    models.set_status(tasting_id, "registration")
    token = models.register_participant(tasting_id, "Гость")
    models.set_status(tasting_id, "round_nose")

    page = client.get(f"/me/{token}").text
    assert "<optgroup" in page
    assert 'label="японский"' in page
    for row in models.list_whiskies():
        assert f'>{escape(row["name"])}</option>' in page


def test_a_second_whisky_with_the_same_name_is_refused(admin):
    """Два одинаковых названия в списке ответов неразличимы.

    Гость выбирает не тот и получает ноль за верно названный виски —
    объяснить это не сможет ни он, ни ведущий.
    """
    admin.post(
        "/admin/whiskies",
        data={"name": "Кемля Односолодовая", "wclass": "односолодовый (не Шотландия)"},
        follow_redirects=True,
    )
    # Тот же виски, набранный иначе: лишние пробелы и другой регистр.
    page = admin.post(
        "/admin/whiskies",
        data={"name": "  кемля   ОДНОСОЛОДОВАЯ ", "wclass": "односолодовый (не Шотландия)"},
        follow_redirects=True,
    ).text
    assert "уже есть в справочнике" in page
    same = [w for w in models.list_whiskies() if w["name"].casefold().startswith("кемля")]
    assert len(same) == 1, "второй записи появиться не должно"
    # Сравнение не по-английски: LIKE и NOCASE в SQLite кириллицу не знают.
    assert models.whisky_by_name("КЕМЛЯ ОДНОСОЛОДОВАЯ")["id"] == same[0]["id"]
