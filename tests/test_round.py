"""Раунд: расстановка образцов, черновик, отправка, счётчик сдавших."""

import pytest

from app import models


@pytest.fixture
def tasting():
    """Дегустация с тремя образцами, открытым раундом по запаху и двумя гостями."""
    tasting_id = models.create_tasting("Первая", None, "class")
    ids = [
        models.save_whisky({"name": name, "wclass": "односолодовый скотч"})
        for name in ("Aberlour Suthainn", "The Dalmore The Quartet", "Kemlya American Oak")
    ]
    for whisky_id in ids:
        models.add_whisky_to_tasting(tasting_id, whisky_id)
    models.set_status(tasting_id, "registration")
    tokens = [models.register_participant(tasting_id, name) for name in ("Саша", "Женя")]
    models.set_status(tasting_id, "round_nose")
    return {
        "id": tasting_id,
        "whiskies": ids,
        "tokens": tokens,
        "people": [models.get_participant_by_token(t)["id"] for t in tokens],
    }


def test_round_comes_from_the_status(tasting):
    assert models.open_round(models.get_tasting(tasting["id"])) == "nose"
    models.set_status(tasting["id"], "round_palate")
    assert models.open_round(models.get_tasting(tasting["id"])) == "palate"


def test_choices_are_alphabetical_not_in_sample_order(tasting):
    """Список в порядке номеров образцов сам был бы ответом."""
    names = [row["name"] for row in models.round_choices(tasting["id"])]
    assert names == sorted(names, key=str.casefold)


def test_draft_is_saved_and_read_back(tasting):
    me = tasting["people"][0]
    models.save_round_draft(me, "nose", {1: tasting["whiskies"][0], 2: tasting["whiskies"][1]})
    assert models.get_answers(me, "nose") == {1: tasting["whiskies"][0], 2: tasting["whiskies"][1]}
    assert models.round_submitted(me, "nose") is False


def test_one_name_cannot_go_to_two_samples(tasting):
    me = tasting["people"][0]
    with pytest.raises(ValueError, match="двум образцам"):
        models.save_round_draft(me, "nose", {1: tasting["whiskies"][0], 2: tasting["whiskies"][0]})


def test_swapping_two_names_is_allowed(tasting):
    """Передумал и поменял местами — обычное дело, UNIQUE мешать не должен."""
    me = tasting["people"][0]
    first, second = tasting["whiskies"][0], tasting["whiskies"][1]
    models.save_round_draft(me, "nose", {1: first, 2: second})
    models.save_round_draft(me, "nose", {1: second, 2: first})
    assert models.get_answers(me, "nose") == {1: second, 2: first}


def test_a_whisky_from_outside_the_tasting_is_refused(tasting):
    stranger = models.save_whisky({"name": "Ardbeg 10"})
    with pytest.raises(ValueError, match="нет в составе"):
        models.save_round_draft(tasting["people"][0], "nose", {1: stranger})


def test_submit_needs_every_sample(tasting):
    me = tasting["people"][0]
    models.save_round_draft(me, "nose", {1: tasting["whiskies"][0]})
    with pytest.raises(ValueError, match="1 из 3"):
        models.submit_round(me, "nose")


def test_submitted_answer_is_frozen(tasting):
    me = tasting["people"][0]
    models.save_round_draft(
        me, "nose", dict(zip((1, 2, 3), tasting["whiskies"]))
    )
    models.submit_round(me, "nose")
    assert models.round_submitted(me, "nose") is True
    with pytest.raises(ValueError, match="уже отправлен"):
        models.save_round_draft(me, "nose", {1: tasting["whiskies"][1]})
    with pytest.raises(ValueError, match="уже отправлен"):
        models.submit_round(me, "nose")


def test_rounds_are_stored_apart(tasting):
    """Ответ по запаху не должен подсказывать в раунде по вкусу."""
    me = tasting["people"][0]
    models.save_round_draft(me, "nose", dict(zip((1, 2, 3), tasting["whiskies"])))
    models.submit_round(me, "nose")
    assert models.get_answers(me, "palate") == {}
    assert models.round_submitted(me, "palate") is False


def test_progress_counts_only_submitted(tasting):
    first, second = tasting["people"]
    assert models.round_progress(tasting["id"], "nose") == (0, 2)
    models.save_round_draft(first, "nose", dict(zip((1, 2, 3), tasting["whiskies"])))
    assert models.round_progress(tasting["id"], "nose") == (0, 2), "черновик — не сдача"
    models.submit_round(first, "nose")
    assert models.round_progress(tasting["id"], "nose") == (1, 2)
    models.save_round_draft(second, "nose", dict(zip((1, 2, 3), tasting["whiskies"])))
    models.submit_round(second, "nose")
    assert models.round_progress(tasting["id"], "nose") == (2, 2)


def test_ratings_keep_tags_of_both_rounds(tasting):
    """Оценка одна на образец, а теги у запаха и вкуса свои."""
    me = tasting["people"][0]
    models.save_round_draft(me, "nose", {}, {1: 80}, {1: "торф, йод"})
    models.set_status(tasting["id"], "round_palate")
    models.save_round_draft(me, "palate", {}, {}, {1: "дым, соль"})
    stored = models.get_ratings(me)[1]
    assert stored["score"] == 80, "оценка из первого раунда не должна пропасть"
    assert "торф, йод" in stored["tags"] and "дым, соль" in stored["tags"]


# ── страница участника ─────────────────────────────────────────────────────


def test_page_shows_the_round(client, tasting):
    page = client.get(f"/me/{tasting['tokens'][0]}").text
    assert "Раунд по запаху" in page
    assert "Образец 1" in page and "Образец 3" in page
    # Названия есть как варианты выбора, но что где налито — не сказано нигде.
    assert "Kemlya American Oak" in page
    assert "sample_1" in page


def test_draft_autosave_over_http(client, tasting):
    token = tasting["tokens"][0]
    response = client.post(
        f"/me/{token}/draft",
        json={"answers": {"1": str(tasting["whiskies"][0])}, "scores": {"1": "70"}, "tags": {"1": "мёд"}},
    )
    assert response.status_code == 200 and response.json() == {"ok": True}
    me = tasting["people"][0]
    assert models.get_answers(me, "nose") == {1: tasting["whiskies"][0]}
    assert models.get_ratings(me)[1]["score"] == 70


def test_duplicate_over_http_is_refused(client, tasting):
    ids = tasting["whiskies"]
    response = client.post(
        f"/me/{tasting['tokens'][0]}/draft",
        json={"answers": {"1": str(ids[0]), "2": str(ids[0])}},
    )
    assert response.status_code == 400
    assert "двум образцам" in response.json()["error"]


def test_submit_over_http_freezes_the_page(client, tasting):
    token = tasting["tokens"][0]
    ids = tasting["whiskies"]
    response = client.post(
        f"/me/{token}/submit",
        data={f"sample_{n}": str(w) for n, w in zip((1, 2, 3), ids)},
        follow_redirects=True,
    )
    assert "Ответ принят" in response.text
    assert "Отправить ответ" not in response.text


def test_incomplete_submit_says_what_is_missing(client, tasting):
    response = client.post(
        f"/me/{tasting['tokens'][0]}/submit",
        data={"sample_1": str(tasting["whiskies"][0])},
        follow_redirects=True,
    )
    assert "1 из 3" in response.text


def test_no_round_no_answers(client, tasting):
    """Пока раунд не открыт, принимать ответы нельзя вовсе."""
    models.set_status(tasting["id"], "round_palate")
    models.set_status(tasting["id"], "scoring")
    response = client.post(f"/me/{tasting['tokens'][0]}/draft", json={"answers": {}})
    assert response.status_code == 409


def test_admin_sees_the_counter(admin, tasting):
    me = tasting["people"][0]
    models.save_round_draft(me, "nose", dict(zip((1, 2, 3), tasting["whiskies"])))
    models.submit_round(me, "nose")
    page = admin.get(f"/admin/tastings/{tasting['id']}").text
    assert "Раунд по запаху идёт" in page
    assert "1 из 2" in page
