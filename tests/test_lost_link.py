"""Потерянная личная ссылка — самая частая беда гостя.

Три пути её вернуть, и каждый нужен: телефон помнит сам, ведущий видит все
ссылки в админке, гость оставил контакт и ссылку можно прислать.
"""

import pytest

from app import models


@pytest.fixture
def open_tasting():
    tasting_id = models.create_tasting("Первая", None, "class")
    models.set_status(tasting_id, "registration")
    return models.get_tasting(tasting_id)["public_code"]


def _join(client, code, name="Саша", contact=""):
    response = client.post(
        f"/join/{code}", data={"name": name, "contact": contact}, follow_redirects=False
    )
    return response.headers["location"].removeprefix("/me/")


# ── телефон помнит ─────────────────────────────────────────────────────────


def test_the_phone_remembers_the_page(client, open_tasting):
    """Вкладка закрылась — с главной страница находится сама."""
    _join(client, open_tasting)
    page = client.get("/").text
    assert "С возвращением, Саша" in page
    assert "Открыть свою страницу" in page


def test_the_registration_page_offers_the_way_back(client, open_tasting):
    """Иначе гость запишется вторым участником с тем же именем."""
    _join(client, open_tasting)
    page = client.get(f"/join/{open_tasting}").text
    assert "Вы уже записаны" in page
    assert "Саша" in page


def test_a_fresh_phone_sees_no_one_elses_page(open_tasting):
    """Кука — фактически пропуск, чужому браузеру ничего доставаться не должно."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as first:
        _join(first, open_tasting)
    with TestClient(app) as stranger:
        assert "С возвращением" not in stranger.get("/").text


def test_opening_the_page_by_link_also_remembers_it(client, open_tasting):
    token = _join(client, open_tasting)
    client.cookies.clear()
    assert "С возвращением" not in client.get("/").text

    client.get(f"/me/{token}")
    assert "С возвращением" in client.get("/").text


def test_a_deleted_participant_does_not_haunt_the_home_page(client, open_tasting):
    """Кука пережила базу — предлагать несуществующую страницу нельзя."""
    token = _join(client, open_tasting)
    from app.db import connect

    with connect() as conn:
        conn.execute("DELETE FROM participant WHERE join_token = ?", (token,))
    assert "С возвращением" not in client.get("/").text


# ── контакт при регистрации ────────────────────────────────────────────────


def test_contact_is_optional(client, open_tasting):
    token = _join(client, open_tasting, contact="")
    assert models.get_participant_by_token(token)["contact"] is None


def test_contact_is_saved_as_written(client, open_tasting):
    token = _join(client, open_tasting, contact="@sasha или +7 900 000-00-00")
    assert models.get_participant_by_token(token)["contact"] == "@sasha или +7 900 000-00-00"


def test_a_very_long_contact_is_trimmed_not_rejected(client, open_tasting):
    """Гость на вечеринке не должен спорить с формой из-за длины поля."""
    token = _join(client, open_tasting, contact="я" * 500)
    assert len(models.get_participant_by_token(token)["contact"]) == models.MAX_CONTACT_LENGTH


def test_the_form_asks_for_a_contact(client, open_tasting):
    page = client.get(f"/join/{open_tasting}").text
    assert "Куда прислать ссылку" in page
    assert "необязательно" in page


# ── ведущий видит ссылки ───────────────────────────────────────────────────


def test_the_admin_sees_every_personal_link(admin, client, open_tasting):
    token = _join(client, open_tasting, contact="@sasha")
    tasting_id = models.get_tasting_by_code(open_tasting)["id"]

    page = admin.get(f"/admin/tastings/{tasting_id}").text
    assert f"/me/{token}" in page, "ведущий должен уметь вернуть ссылку"
    assert "@sasha" in page, "и видеть, куда её прислать"
    assert "потерял ссылку" in page


def test_personal_links_use_the_public_address(admin, client, open_tasting, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://raikhinwhiskey.duckdns.org")
    _join(client, open_tasting)
    tasting_id = models.get_tasting_by_code(open_tasting)["id"]
    page = admin.get(f"/admin/tastings/{tasting_id}").text
    assert "https://raikhinwhiskey.duckdns.org/me/" in page


def test_the_guest_sees_their_own_link_to_copy(client, open_tasting, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://raikhinwhiskey.duckdns.org")
    token = _join(client, open_tasting)
    page = client.get(f"/me/{token}").text
    assert f"https://raikhinwhiskey.duckdns.org/me/{token}" in page
