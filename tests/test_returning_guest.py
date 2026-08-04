"""Гость пришёл на вторую дегустацию: не заставлять его делать всё заново."""

import pytest

from app import models


def _tasting(title):
    tasting_id = models.create_tasting(title, None, "class")
    models.set_status(tasting_id, "registration")
    return tasting_id, models.get_tasting(tasting_id)["public_code"]


def _join(client, code, name="Саша", contact=""):
    return client.post(
        f"/join/{code}", data={"name": name, "contact": contact}, follow_redirects=False
    ).headers["location"].removeprefix("/me/")


@pytest.fixture
def returning(client):
    """Гость с прошлой дегустации: телеграм привязан, телефон тот же."""
    _, first_code = _tasting("Прошлая")
    token = _join(client, first_code, "Саша", "@sasha")
    models.link_telegram(token, 111, "sasha")
    second_id, second_code = _tasting("Новая")
    return {"token": token, "code": second_code, "id": second_id}


def test_the_old_page_is_not_offered_on_a_new_tasting(client, returning):
    """Раньше страница звала «вернуться» на прошлую дегустацию — это ошибка."""
    page = client.get(f"/join/{returning['code']}").text
    assert "Вы уже записаны" not in page
    assert "С возвращением" in page
    assert "Записаться" in page


def test_name_and_contact_are_prefilled(client, returning):
    page = client.get(f"/join/{returning['code']}").text
    assert 'value="Саша"' in page
    assert 'value="@sasha"' in page


def test_telegram_carries_over_without_asking(client, returning):
    page = client.get(f"/join/{returning['code']}").text
    assert "привязывать заново не нужно" in page

    token = _join(client, returning["code"], "Саша", "@sasha")
    fresh = models.get_participant_by_token(token)
    assert fresh["tg_chat_id"] == 111
    assert fresh["tg_username"] == "sasha"


def test_the_new_page_does_not_nag_about_the_bot(client, returning):
    token = _join(client, returning["code"], "Саша", "@sasha")
    page = client.get(f"/me/{token}").text
    assert "Телеграм привязан" in page
    assert "Привязать телеграм →" not in page


def test_a_guest_without_a_linked_bot_carries_nothing(client):
    _, first_code = _tasting("Прошлая")
    _join(client, first_code, "Женя")
    _, second_code = _tasting("Новая")

    token = _join(client, second_code, "Женя")
    assert models.get_participant_by_token(token)["tg_chat_id"] is None


def test_a_stranger_phone_carries_nothing(returning):
    """Перенос опирается на тот же телефон, а не на совпадение имени."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as stranger:
        token = _join(stranger, returning["code"], "Саша", "@sasha")
    assert models.get_participant_by_token(token)["tg_chat_id"] is None


# ── подсказка ведущему ─────────────────────────────────────────────────────


def test_a_matching_contact_is_only_a_hint_for_the_host(admin, client, returning):
    """По строчке контакта связывать нельзя: туда можно вписать чужой ник."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as other_phone:
        token = _join(other_phone, returning["code"], "Саша", "@sasha")
    new_id = models.get_participant_by_token(token)["id"]

    assert models.get_participant_by_token(token)["tg_chat_id"] is None, "молча — нет"
    match = models.matching_telegram(returning["id"], new_id)
    assert match is not None and match["title"] == "Прошлая"

    page = admin.get(f"/admin/tastings/{returning['id']}").text
    assert "перенести с «Прошлая»" in page

    admin.post(
        f"/admin/tastings/{returning['id']}/participants/{new_id}/carry",
        follow_redirects=True,
    )
    assert models.get_participant_by_token(token)["tg_chat_id"] == 111


def test_no_contact_no_match(client, returning):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as other_phone:
        token = _join(other_phone, returning["code"], "Саша")
    new_id = models.get_participant_by_token(token)["id"]
    assert models.matching_telegram(returning["id"], new_id) is None


def test_an_already_linked_participant_needs_no_hint(client, returning):
    token = _join(client, returning["code"], "Саша", "@sasha")
    person = models.get_participant_by_token(token)
    assert models.matching_telegram(returning["id"], person["id"]) is None
