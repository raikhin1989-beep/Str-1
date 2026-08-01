"""Исходящие для раннера: сервер не может писать в телеграм сам."""

import pytest

from app import broadcast, models

SECRET = "test-webhook-secret-0123456789"


@pytest.fixture(autouse=True)
def bot(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:тест")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)


@pytest.fixture
def finished():
    tasting_id = models.create_tasting("Первая", None, "class")
    for name in ("Ardbeg 10", "Talisker 10", "Oban 14"):
        models.add_whisky_to_tasting(tasting_id, models.save_whisky({"name": name}))
    models.set_status(tasting_id, "registration")
    tokens = {n: models.register_participant(tasting_id, n) for n in ("Саша", "Женя")}
    people = {n: models.get_participant_by_token(t)["id"] for n, t in tokens.items()}
    models.link_telegram(tokens["Саша"], 111, "sasha")

    truth = models.tasting_truth(tasting_id)
    models.set_status(tasting_id, "round_nose")
    models.save_round_draft(people["Саша"], "nose", dict(truth))
    models.set_status(tasting_id, "round_palate")
    models.set_status(tasting_id, "scoring")
    models.compute_results(tasting_id)
    return {"id": tasting_id, "people": people}


def test_the_outbox_hides_behind_the_secret(client, finished):
    assert client.get("/internal/outbox/не-тот-секрет").status_code == 404
    assert client.get(f"/internal/outbox/{SECRET}").status_code == 200


def test_only_linked_participants_are_listed(client, finished):
    body = client.get(f"/internal/outbox/{SECRET}").json()
    assert body["count"] == 1
    message = body["messages"][0]
    assert message["chat_id"] == 111
    assert message["participant_id"] == finished["people"]["Саша"]
    assert "итоги" in message["text"] and "/results/" in message["text"]


def test_nothing_is_marked_until_the_runner_says_so(client, finished):
    client.get(f"/internal/outbox/{SECRET}")
    assert models.delivered(finished["id"], broadcast.KIND) == set()


def test_the_runner_reports_back_and_the_message_disappears(client, finished):
    sasha = finished["people"]["Саша"]
    response = client.post(f"/internal/outbox/{SECRET}/delivered", json={"ids": [sasha]})
    assert response.json() == {"ok": True, "marked": 1}
    assert models.delivered(finished["id"], broadcast.KIND) == {sasha}
    assert client.get(f"/internal/outbox/{SECRET}").json()["count"] == 0


def test_marking_needs_the_secret_too(client, finished):
    response = client.post("/internal/outbox/чужой/delivered", json={"ids": [1]})
    assert response.status_code == 404


def test_an_unfinished_evening_has_nothing_to_send(client):
    models.set_status(models.create_tasting("Идёт", None, "class"), "registration")
    assert client.get(f"/internal/outbox/{SECRET}").json()["messages"] == []


def test_without_a_bot_secret_the_path_does_not_exist(client, finished, monkeypatch):
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    assert client.get(f"/internal/outbox/{SECRET}").status_code == 404
