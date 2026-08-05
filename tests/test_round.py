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


def test_a_whisky_from_the_catalogue_is_a_valid_answer(tasting):
    """Назвать можно и то, чего на столе нет: за этим и нужен частичный балл."""
    other = models.save_whisky({"name": "Ardbeg 10"})
    models.save_round_draft(tasting["people"][0], "nose", {1: other})
    assert models.get_answers(tasting["people"][0], "nose") == {1: other}


def test_a_whisky_that_does_not_exist_is_refused(tasting):
    with pytest.raises(ValueError, match="нет в составе"):
        models.save_round_draft(tasting["people"][0], "nose", {1: 999999})


def test_the_narrow_mode_still_allows_only_what_is_poured():
    """Режим полегче: список сужен до налитого, чужое не принимается."""
    tasting_id = models.create_tasting("Полегче", None, "class", "tasting")
    poured = models.save_whisky({"name": "Oban 14"})
    models.add_whisky_to_tasting(tasting_id, poured)
    outsider = models.save_whisky({"name": "Ardbeg 10"})
    models.set_status(tasting_id, "registration")
    token = models.register_participant(tasting_id, "Саша")
    me = models.get_participant_by_token(token)["id"]
    models.set_status(tasting_id, "round_nose")

    assert [row["name"] for row in models.round_choices(tasting_id)] == ["Oban 14"]
    with pytest.raises(ValueError, match="нет в составе"):
        models.save_round_draft(me, "nose", {1: outsider})


def test_the_scope_is_frozen_once_the_rounds_start(tasting):
    """Половина стола уже ответила из одного списка — менять его поздно."""
    models.update_tasting(tasting["id"], "Первая", None, "class", "tasting")
    assert models.get_tasting(tasting["id"])["answer_scope"] == "catalogue"


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


# ── раунд по вкусу ─────────────────────────────────────────────────────────


def test_palate_round_starts_empty(client, tasting):
    """Свои ответы первого раунда участник видеть не должен: за совпадение даётся балл."""
    token = tasting["tokens"][0]
    ids = tasting["whiskies"]
    client.post(f"/me/{token}/submit", data={f"sample_{n}": str(w) for n, w in zip((1, 2, 3), ids)})
    models.set_status(tasting["id"], "round_palate")

    page = client.get(f"/me/{token}").text
    assert "Раунд по вкусу" in page
    assert "selected" not in page, "ни один вариант не должен быть выбран заранее"
    assert models.get_answers(tasting["people"][0], "palate") == {}


def test_round_two_cannot_open_before_round_one(tasting):
    """Прыгнуть из регистрации сразу во второй раунд нельзя."""
    other = models.create_tasting("Вторая", None, "class")
    models.set_status(other, "registration")
    with pytest.raises(ValueError, match="не разрешён"):
        models.set_status(other, "round_palate")


def test_closing_a_round_freezes_unfinished_drafts(tasting):
    """Забыл нажать «Отправить» — ответ всё равно засчитан, а не потерян."""
    lazy = tasting["people"][1]
    models.save_round_draft(lazy, "nose", dict(zip((1, 2, 3), tasting["whiskies"])))
    assert models.round_submitted(lazy, "nose") is False

    models.set_status(tasting["id"], "round_palate")
    assert models.round_submitted(lazy, "nose") is True
    assert models.get_answers(lazy, "nose") == dict(zip((1, 2, 3), tasting["whiskies"]))


def test_a_frozen_draft_cannot_be_edited_afterwards(tasting):
    me = tasting["people"][0]
    models.save_round_draft(me, "nose", {1: tasting["whiskies"][0]})
    models.set_status(tasting["id"], "round_palate")
    with pytest.raises(ValueError, match="уже отправлен"):
        models.save_round_draft(me, "nose", {1: tasting["whiskies"][1]})


def test_palate_answers_are_independent(tasting):
    """В двух раундах можно ответить по-разному — на то и бонус за постоянство."""
    me = tasting["people"][0]
    first, second, third = tasting["whiskies"]
    models.save_round_draft(me, "nose", {1: first, 2: second, 3: third})
    models.submit_round(me, "nose")
    models.set_status(tasting["id"], "round_palate")

    models.save_round_draft(me, "palate", {1: second, 2: first, 3: third})
    models.submit_round(me, "palate")
    assert models.get_answers(me, "nose") == {1: first, 2: second, 3: third}
    assert models.get_answers(me, "palate") == {1: second, 2: first, 3: third}


def test_tags_of_the_second_round_do_not_erase_the_first(client, tasting):
    token = tasting["tokens"][0]
    client.post(f"/me/{token}/draft", json={"tags": {"1": "торф и йод"}})
    models.set_status(tasting["id"], "round_palate")
    client.post(f"/me/{token}/draft", json={"tags": {"1": "дым и соль"}})

    page = client.get(f"/me/{token}").text
    assert "дым и соль" in page
    assert "торф и йод" not in page, "теги запаха во втором раунде не показываем"
    stored = models.get_ratings(tasting["people"][0])[1]["tags"]
    assert "торф и йод" in stored and "дым и соль" in stored


def test_admin_counter_follows_the_second_round(admin, tasting):
    models.set_status(tasting["id"], "round_palate")
    me = tasting["people"][0]
    models.save_round_draft(me, "palate", dict(zip((1, 2, 3), tasting["whiskies"])))
    models.submit_round(me, "palate")
    page = admin.get(f"/admin/tastings/{tasting['id']}").text
    assert "Раунд по вкусу идёт" in page
    assert "1 из 2" in page


# ── кривой запрос — это отказ, а не сбой ───────────────────────────────────
#
# Найдено обстрелом после живого теста, где «Internal Server Error» появился
# на ответе второго участника. Ни один из этих случаев браузер сам не пришлёт,
# но пятисотка посреди вечера выглядит как сломанный сайт, и разбираться с ней
# некогда — отвечать надо отказом.

BAD_DRAFTS = [
    {"answers": {"1": [1]}},                  # TypeError в int()
    {"answers": "строка"},                    # AttributeError на .items()
    {"answers": [1, 2]},
    {"scores": {"1": "9" * 30}},              # OverflowError уже внутри SQLite
    {"scores": {"1": {"a": 1}}},
    {"tags": "строка"},
    {"answers": {"1e999": "1"}},
]


@pytest.mark.parametrize("payload", BAD_DRAFTS)
def test_a_malformed_draft_is_refused_not_crashed(client, tasting, payload):
    response = client.post(f"/me/{tasting['tokens'][1]}/draft", json=payload)
    assert response.status_code == 400, response.text
    assert response.json()["ok"] is False


def test_a_body_that_is_not_json_is_refused(client, tasting):
    response = client.post(
        f"/me/{tasting['tokens'][1]}/draft",
        content=b"{broken",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400


def test_a_nested_tag_does_not_break_the_draft(client, tasting):
    """Заметка — это память о вечере, а не данные для зачёта: приводим
    к строке и сохраняем, вместо того чтобы ронять запрос."""
    response = client.post(
        f"/me/{tasting['tokens'][1]}/draft",
        json={"tags": {"1": {"вложенный": "объект"}}},
    )
    assert response.status_code == 200


BAD_FORMS = [
    {"sample_1": "1", "score_1": "9" * 30},
    {"sample_99999999999999999999999": "1"},
    {"sample_x": "1"},
    {"score_1": "не число"},
]


@pytest.mark.parametrize("data", BAD_FORMS)
def test_a_malformed_submit_is_refused_not_crashed(client, tasting, data):
    response = client.post(f"/me/{tasting['tokens'][1]}/submit", data=data, follow_redirects=False)
    assert response.status_code < 500, response.text


# ── ответ не должен попасть не в тот раунд ─────────────────────────────────


def test_a_stale_form_does_not_land_in_the_next_round(client, tasting):
    """Поймано на живой дегустации 5 августа.

    Гость держит открытой страницу раунда по запаху, ведущий тем временем
    открывает вкус, гость дожимает «Отправить» — и его ответ по запаху молча
    ложится в раунд вкуса. Настоящего ответа по вкусу он больше не даст:
    отправленное заморожено. Со стороны это выглядит как «ответ не пришёл».
    """
    token = tasting["tokens"][1]
    person = tasting["people"][1]
    truth = models.tasting_truth(tasting["id"])
    stale = {f"sample_{no}": str(whisky_id) for no, whisky_id in truth.items()}
    stale["round"] = "nose"

    models.set_status(tasting["id"], "round_palate")
    response = client.post(f"/me/{token}/submit", data=stale, follow_redirects=False)

    assert response.status_code == 409
    assert models.get_answers(person, "palate") == {}, "чужой раунд не должен записаться"


def test_the_guest_is_told_what_happened(client, tasting):
    """Отказ без объяснения посреди вечера — это тупик."""
    token = tasting["tokens"][0]
    models.set_status(tasting["id"], "round_palate")
    page = client.post(
        f"/me/{token}/submit",
        data={"round": "nose", "sample_1": ""},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert "ведущий перешёл к другому раунду" in page.text
    assert "по вкусу" in page.text


def test_a_stale_draft_is_refused_too(client, tasting):
    token = tasting["tokens"][0]
    models.set_status(tasting["id"], "round_palate")
    response = client.post(f"/me/{token}/draft", json={"round": "nose", "answers": {}})
    assert response.status_code == 409
    assert "другому раунду" in response.json()["error"]


def test_the_current_round_still_goes_through(client, tasting):
    """Проверка не должна мешать нормальному ходу вечера."""
    token = tasting["tokens"][0]
    truth = models.tasting_truth(tasting["id"])
    data = {f"sample_{no}": str(whisky_id) for no, whisky_id in truth.items()}
    data["round"] = "nose"
    assert client.post(f"/me/{token}/submit", data=data, follow_redirects=False).status_code == 303
    assert models.get_answers(tasting["people"][0], "nose") == truth


def test_a_stray_post_to_the_page_is_not_a_dead_end(client, tasting):
    """Голый 405 посреди вечера гость починить не может."""
    response = client.post(f"/me/{tasting['tokens'][0]}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith(tasting["tokens"][0])


def test_the_guest_can_name_the_class_instead_of_the_whisky(client, tasting):
    """Сквозняком: поле есть на странице, ответ доходит до базы и даёт балл."""
    token = tasting["tokens"][0]
    person = tasting["people"][0]

    page = client.get(f"/me/{token}").text
    assert 'name="class_1"' in page
    assert "Или хотя бы класс" in page

    truth = models.tasting_truth(tasting["id"])
    poured = models.get_whisky(truth[1])
    response = client.post(
        f"/me/{token}/submit",
        data={"round": "nose", "sample_1": "", "class_1": poured["wclass"]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert models.get_categories(person, "nose") == {1: poured["wclass"]}

    score = models.score_tasting(tasting["id"])[person]
    assert score.points_partial >= 1, "класс назван верно — балл должен быть"


def test_a_region_tasting_offers_regions(client):
    """Список зависит от того, как заведена дегустация."""
    tasting_id = models.create_tasting("По регионам", None, "region")
    for row in models.list_whiskies()[:3]:
        models.add_whisky_to_tasting(tasting_id, row["id"])
    models.set_status(tasting_id, "registration")
    token = models.register_participant(tasting_id, "Гость")
    models.set_status(tasting_id, "round_nose")

    page = client.get(f"/me/{token}").text
    assert "Или хотя бы регион" in page
    assert "односолодовый скотч" not in page.split('name="class_1"')[1].split("</select>")[0]
