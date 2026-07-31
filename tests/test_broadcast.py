"""Рассылка итогов в телеграм."""

import pytest

from app import broadcast, models, telegram


@pytest.fixture
def sent(monkeypatch):
    """Бот «настроен», но в сеть не ходит. Список — что и кому ушло бы."""
    box = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:тест")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret-0123456789")
    monkeypatch.setattr(
        telegram, "send_message", lambda chat_id, text: box.append((chat_id, text)) or True
    )
    return box


@pytest.fixture
def finished():
    """Сыгранный и посчитанный вечер: двое с телеграмом, один без."""
    tasting_id = models.create_tasting("Первая", None, "class")
    for name in ("Ardbeg 10", "Talisker 10", "Oban 14"):
        models.add_whisky_to_tasting(tasting_id, models.save_whisky({"name": name}))
    models.set_status(tasting_id, "registration")
    tokens = {
        name: models.register_participant(tasting_id, name)
        for name in ("Саша", "Женя", "Костя")
    }
    people = {name: models.get_participant_by_token(t)["id"] for name, t in tokens.items()}
    models.link_telegram(tokens["Саша"], 111, "sasha")
    models.link_telegram(tokens["Женя"], 222, None)

    truth = models.tasting_truth(tasting_id)
    models.set_status(tasting_id, "round_nose")
    models.save_round_draft(people["Саша"], "nose", dict(truth))
    models.set_status(tasting_id, "round_palate")
    models.save_round_draft(people["Саша"], "palate", dict(truth))
    models.set_status(tasting_id, "scoring")
    models.compute_results(tasting_id)
    return {"id": tasting_id, "people": people, "tokens": tokens}


URL = "https://raikhinwhiskey.duckdns.org/results/код"


def test_everyone_linked_gets_a_personal_message(finished, sent):
    report = broadcast.send_results(finished["id"], URL)
    assert sorted(report["sent"]) == ["Женя", "Саша"]
    assert report["unlinked"] == ["Костя"]
    assert {chat_id for chat_id, _ in sent} == {111, 222}


def test_the_message_has_place_points_and_a_link(finished, sent):
    broadcast.send_results(finished["id"], URL)
    to_sasha = next(text for chat_id, text in sent if chat_id == 111)
    assert "Саша" in to_sasha
    assert "место" in to_sasha and "Очков" in to_sasha
    assert "Ardbeg 10" in to_sasha, "что именно угадал"
    assert "Топ-3" in to_sasha
    assert URL in to_sasha


def test_a_player_who_guessed_nothing_is_told_gently(finished, sent):
    broadcast.send_results(finished["id"], URL)
    to_zhenya = next(text for chat_id, text in sent if chat_id == 222)
    assert "мимо" in to_zhenya


def test_pressing_again_sends_nothing_twice(finished, sent):
    broadcast.send_results(finished["id"], URL)
    assert len(sent) == 2
    again = broadcast.send_results(finished["id"], URL)
    assert len(sent) == 2, "второй раз никому"
    assert sorted(again["skipped"]) == ["Женя", "Саша"]
    assert again["sent"] == []


def test_a_failed_send_is_retried_next_time(finished, monkeypatch):
    """Не дошло — не отмечаем, значит повтор догонит."""
    attempts = []

    def flaky(chat_id, text):
        attempts.append(chat_id)
        return chat_id != 222

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:тест")
    monkeypatch.setattr(telegram, "send_message", flaky)

    first = broadcast.send_results(finished["id"], URL)
    assert first["failed"] == ["Женя"] and first["sent"] == ["Саша"]

    monkeypatch.setattr(telegram, "send_message", lambda chat_id, text: True)
    second = broadcast.send_results(finished["id"], URL)
    assert second["sent"] == ["Женя"], "повтор идёт только к тому, кому не дошло"
    assert second["skipped"] == ["Саша"]


def test_someone_who_links_telegram_later_gets_it_on_the_next_press(finished, sent):
    broadcast.send_results(finished["id"], URL)
    models.link_telegram(finished["tokens"]["Костя"], 333, None)
    report = broadcast.send_results(finished["id"], URL)
    assert report["sent"] == ["Костя"]
    assert 333 in {chat_id for chat_id, _ in sent}


def test_broadcast_refuses_before_the_results_are_in(sent):
    tasting_id = models.create_tasting("Ещё идёт", None, "class")
    with pytest.raises(ValueError, match="итоги ещё не подведены"):
        broadcast.send_results(tasting_id, URL)


def test_names_are_escaped(finished, sent):
    """Имя пишет гость, а сообщение уходит с parse_mode=HTML."""
    from app.db import connect

    # Имя правим прямо в базе: через регистрацию его уже не поменять,
    # а проверить надо именно разметку в имени.
    with connect() as conn:
        conn.execute(
            "UPDATE participant SET name = ? WHERE id = ?",
            ("<b>Саша</b>", finished["people"]["Саша"]),
        )
    models.compute_results(finished["id"])
    broadcast.send_results(finished["id"], URL)
    to_sasha = next(text for chat_id, text in sent if chat_id == 111)
    assert "&lt;b&gt;Саша&lt;/b&gt;" in to_sasha


def test_admin_button_reports_who_got_it(admin, finished, sent):
    response = admin.post(
        f"/admin/tastings/{finished['id']}/broadcast", follow_redirects=True
    )
    assert "отправлено: 2" in response.text
    assert "без телеграма: Костя" in response.text
