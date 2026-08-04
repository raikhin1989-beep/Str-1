"""Страница гостя оживает сама, а список виски идёт по алфавиту."""

import pytest

from app import models


@pytest.fixture
def guest():
    tasting_id = models.create_tasting("Первая", None, "class")
    # Названия нарочно вперемешку: латиница, кириллица, разный регистр.
    for name in ("Кемля Американ Оук", "далмор квотер", "Aberlour Suthainn", "джек"):
        models.add_whisky_to_tasting(tasting_id, models.save_whisky({"name": name}))
    models.set_status(tasting_id, "registration")
    token = models.register_participant(tasting_id, "Саша")
    return {"id": tasting_id, "token": token}


# ── порядок названий ───────────────────────────────────────────────────────


def test_names_are_alphabetical_regardless_of_alphabet_and_case(guest):
    """COLLATE NOCASE в SQLite не складывает регистр кириллицы — и список
    получался как попало, хотя в SQL стояло ORDER BY."""
    names = [row["name"] for row in models.round_choices(guest["id"])]
    assert names == sorted(names, key=str.casefold)
    assert names == ["Aberlour Suthainn", "далмор квотер", "джек", "Кемля Американ Оук"]


def test_the_catalogue_is_sorted_the_same_way():
    for name in ("яблочный", "Ardbeg", "Ёлка", "берёзовый"):
        models.save_whisky({"name": name})
    names = [row["name"] for row in models.list_whiskies()]
    assert names == sorted(names, key=str.casefold)


def test_the_round_page_lists_them_in_that_order(client, guest):
    models.set_status(guest["id"], "round_nose")
    page = client.get(f"/me/{guest['token']}").text
    positions = [
        page.index(name)
        for name in ("Aberlour Suthainn", "далмор квотер", "джек", "Кемля Американ Оук")
    ]
    assert positions == sorted(positions), "на странице порядок тот же, что в модели"


# ── страница оживает сама ──────────────────────────────────────────────────


def test_before_the_round_the_guest_is_told_to_wait(client, guest):
    page = client.get(f"/me/{guest['token']}").text
    assert "Ждём ведущего" in page
    assert "Раунд ещё не начался" in page
    assert "disabled" in page, "кнопка должна быть видна, но не нажиматься"
    assert "Образец 1" not in page


def test_the_state_endpoint_follows_the_evening(client, guest):
    state = client.get(f"/api/me/{guest['token']}/state").json()
    assert state == {"status": "registration", "round": None, "submitted": False}

    models.set_status(guest["id"], "round_nose")
    state = client.get(f"/api/me/{guest['token']}/state").json()
    assert state == {"status": "round_nose", "round": "nose", "submitted": False}


def test_the_page_carries_the_state_it_was_drawn_with(client, guest):
    """Скрипт сравнивает опрос с этим — иначе не понять, что изменилось."""
    page = client.get(f"/me/{guest['token']}").text
    assert 'data-source="/api/me/' in page
    assert "&#34;status&#34;: &#34;registration&#34;" in page or '"status": "registration"' in page
    assert "/static/me.js" in page


def test_once_the_round_opens_the_form_replaces_the_waiting(client, guest):
    models.set_status(guest["id"], "round_nose")
    page = client.get(f"/me/{guest['token']}").text
    assert "Ждём ведущего" not in page
    assert "Раунд по запаху" in page
    assert "Образец 1" in page


def test_between_rounds_and_at_scoring_the_guest_is_told_what_is_happening(client, guest):
    models.set_status(guest["id"], "round_nose")
    models.set_status(guest["id"], "round_palate")
    assert "Раунд по вкусу" in client.get(f"/me/{guest['token']}").text

    models.set_status(guest["id"], "scoring")
    page = client.get(f"/me/{guest['token']}").text
    assert "Ведущий считает итоги" in page


def test_the_state_of_a_stranger_is_not_told(client):
    assert client.get("/api/me/такого-токена-нет/state").status_code == 404


def test_a_finished_evening_without_points_still_explains_itself(client, guest):
    """Гость мог записаться и не играть — страница не должна молчать."""
    models.set_status(guest["id"], "round_nose")
    models.set_status(guest["id"], "round_palate")
    models.set_status(guest["id"], "scoring")
    models.compute_results(guest["id"])
    models.set_status(guest["id"], "closed")

    # Убираем строку итогов, как будто считать было нечего.
    from app.db import connect

    with connect() as conn:
        conn.execute("DELETE FROM result")

    page = client.get(f"/me/{guest['token']}").text
    assert "Дегустация окончена" in page
    assert "что было в стаканах" in page
