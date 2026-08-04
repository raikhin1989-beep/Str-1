"""Итоги: подсчёт по базе, таблица, разбор по образцам, экран ведущего."""

import pytest

from app import models


@pytest.fixture
def played():
    """Сыгранный вечер: три образца, двое гостей, оба раунда пройдены."""
    tasting_id = models.create_tasting("Первая", None, "class")
    ids = [
        models.save_whisky({"name": name, "wclass": wclass})
        for name, wclass in (
            ("Aberlour Suthainn", "односолодовый скотч"),
            ("The Dalmore The Quartet", "односолодовый скотч"),
            ("Kemlya American Oak", "односолодовый (не Шотландия)"),
        )
    ]
    for whisky_id in ids:
        models.add_whisky_to_tasting(tasting_id, whisky_id)
    models.set_status(tasting_id, "registration")
    tokens = [models.register_participant(tasting_id, name) for name in ("Саша", "Женя")]
    people = [models.get_participant_by_token(t)["id"] for t in tokens]

    truth = models.tasting_truth(tasting_id)  # номер образца → id виски
    models.set_status(tasting_id, "round_nose")
    # Саша угадывает всё, Женя путает два односолодовых скотча.
    models.save_round_draft(people[0], "nose", dict(truth))
    models.submit_round(people[0], "nose")
    swapped = dict(truth)
    swapped[1], swapped[2] = truth[2], truth[1]
    models.save_round_draft(people[1], "nose", swapped)
    models.submit_round(people[1], "nose")

    models.set_status(tasting_id, "round_palate")
    models.save_round_draft(people[0], "palate", dict(truth))
    models.save_round_draft(people[0 + 1], "palate", dict(truth))
    for person in people:
        models.save_round_draft(person, "palate", dict(truth), {1: 90, 2: 60, 3: 70})
        models.submit_round(person, "palate")

    return {"id": tasting_id, "whiskies": ids, "tokens": tokens, "people": people, "truth": truth}


def test_scoring_uses_the_real_pouring(played):
    scores = models.score_tasting(played["id"])
    winner = scores[played["people"][0]]
    assert winner.points_nose == 9 and winner.clean_nose
    assert winner.total == 3 * 3 + 3 * 2 + 3 + 3 + 3, "оба раунда чисто и постоянство"


def test_category_of_the_tasting_decides_partial_points(played):
    """Уровень «по классу»: два шотландских односолодовых дают частичный балл."""
    loser = models.score_tasting(played["id"])[played["people"][1]]
    assert loser.points_partial == 2, "два промаха, оба в свой же класс"
    assert loser.points_nose == 3, "третий образец угадан"


def test_results_are_written_and_placed(played):
    models.compute_results(played["id"])
    board = models.leaderboard(played["id"])
    assert [row["name"] for row in board] == ["Саша", "Женя"]
    assert [row["place"] for row in board] == [1, 2]
    assert board[0]["total"] > board[1]["total"]


def test_recount_is_idempotent(played):
    models.compute_results(played["id"])
    first = [dict(row) for row in models.leaderboard(played["id"])]
    models.compute_results(played["id"])
    second = [dict(row) for row in models.leaderboard(played["id"])]
    assert [r["total"] for r in first] == [r["total"] for r in second]
    assert len(second) == 2, "пересчёт не должен задваивать строки"


def test_breakdown_says_who_guessed_what(played):
    rows = models.sample_breakdown(played["id"])
    assert len(rows) == 3
    first = rows[0]
    assert first["whisky"]["id"] == played["truth"][1]
    assert first["nose"] == ["Саша"], "Женя перепутала первый образец"
    assert first["palate"] == ["Женя", "Саша"]


def test_whisky_of_the_night_is_the_best_rated(played):
    best = models.whisky_of_the_night(played["id"])
    assert best["sample_no"] == 1 and best["average"] == 90.0
    assert best["whisky"]["id"] == played["truth"][1]


def test_a_guest_who_never_answered_stays_in_the_table():
    """Записался и не играл — ноль и последнее место, но из таблицы не исчезает."""
    tasting_id = models.create_tasting("Тихий вечер", None, "class")
    for name in ("Ardbeg 10", "Talisker 10", "Oban 14"):
        models.add_whisky_to_tasting(tasting_id, models.save_whisky({"name": name}))
    models.set_status(tasting_id, "registration")
    active = models.get_participant_by_token(models.register_participant(tasting_id, "Игрок"))
    models.register_participant(tasting_id, "Молчун")

    models.set_status(tasting_id, "round_nose")
    models.save_round_draft(active["id"], "nose", dict(models.tasting_truth(tasting_id)))
    models.submit_round(active["id"], "nose")
    models.set_status(tasting_id, "round_palate")
    models.set_status(tasting_id, "scoring")
    models.compute_results(tasting_id)

    board = {row["name"]: row for row in models.leaderboard(tasting_id)}
    assert set(board) == {"Игрок", "Молчун"}
    assert board["Молчун"]["total"] == 0
    assert board["Молчун"]["place"] == 2
    scores = models.score_tasting(tasting_id)
    assert scores[active["id"]].answered is True


# ── страницы ───────────────────────────────────────────────────────────────


def _publish(tasting_id):
    models.set_status(tasting_id, "scoring")
    models.compute_results(tasting_id)


def test_results_are_closed_until_the_host_says_so(client, played):
    code = models.get_tasting(played["id"])["public_code"]
    page = client.get(f"/results/{code}")
    assert page.status_code == 200
    assert "Ещё рано" in page.text
    assert "Kemlya American Oak" not in page.text, "что налито — не показываем"


def test_results_page_shows_the_table_and_the_pouring(client, played):
    code = models.get_tasting(played["id"])["public_code"]
    _publish(played["id"])
    page = client.get(f"/results/{code}").text
    assert "Турнирная таблица" in page
    assert "Саша" in page and "Женя" in page
    assert "Kemlya American Oak" in page, "теперь состав можно раскрыть"
    assert "Виски вечера" in page


def test_personal_page_shows_my_own_breakdown(client, played):
    _publish(played["id"])
    page = client.get(f"/me/{played['tokens'][1]}").text
    assert "Ваш результат" in page
    assert "Место 2" in page


def test_board_data_follows_the_evening(client, played):
    code = models.get_tasting(played["id"])["public_code"]
    live = client.get(f"/api/board/{code}").json()
    assert live["rows"] == [], "до подсчёта таблицы нет"

    _publish(played["id"])
    final = client.get(f"/api/board/{code}").json()
    assert [row["name"] for row in final["rows"]] == ["Саша", "Женя"]
    assert final["rows"][0]["place"] == 1


def test_board_shows_the_counter_while_a_round_runs(client):
    tasting_id = models.create_tasting("Идёт", None, "class")
    whisky_id = models.save_whisky({"name": "Ardbeg 10"})
    models.add_whisky_to_tasting(tasting_id, whisky_id)
    models.set_status(tasting_id, "registration")
    models.register_participant(tasting_id, "Гость")
    models.set_status(tasting_id, "round_nose")

    code = models.get_tasting(tasting_id)["public_code"]
    live = client.get(f"/api/board/{code}").json()
    assert live["round"] == "по запаху"
    assert live["submitted"] == 0 and live["participants"] == 1


def test_admin_recount_needs_the_scoring_stage(admin, played):
    response = admin.post(
        f"/admin/tastings/{played['id']}/recount", follow_redirects=True
    )
    assert "Сначала подведите итоги" in response.text

    _publish(played["id"])
    response = admin.post(
        f"/admin/tastings/{played['id']}/recount", follow_redirects=True
    )
    assert "Пересчитано" in response.text


def test_moving_to_scoring_counts_right_away(admin, played):
    """Между «подвести итоги» и первым пересчётом страница не должна пустовать."""
    admin.post(
        f"/admin/tastings/{played['id']}/status",
        data={"status": "scoring"},
        follow_redirects=True,
    )
    assert models.leaderboard(played["id"]), "итоги должны посчитаться сами"


def _headers(html: str) -> list[str]:
    import re
    head = html[html.index("<thead>") : html.index("</thead>")]
    return re.findall(r"<th>([^<]*)</th>", head)


def test_the_total_comes_right_after_the_name(client, played):
    """Главное число таблицы. На телефоне столбцы справа уезжают за край,
    и «Итого» уезжало первым — то есть ровно то, ради чего её открывают."""
    _publish(played["id"])
    code = models.get_tasting(played["id"])["public_code"]
    columns = _headers(client.get(f"/results/{code}").text)
    assert columns[:3] == ["№", "Кто", "Итого"], columns


def test_the_projector_builds_cells_in_the_same_order_as_its_headers():
    """Заголовки в шаблоне, значения в скрипте — разъехаться им ничего
    не мешает, кроме внимания. Проверяем, что не разъехались."""
    from pathlib import Path

    template = Path("app/templates/board.html").read_text(encoding="utf-8")
    script = Path("site/static/board.js").read_text(encoding="utf-8")

    headers = _headers(template)
    order = ["place", "name", "total", "nose", "palate", "partial", "bonus"]
    cells = [key for key in order if f"row.{key}" in script]
    positions = sorted(cells, key=lambda key: script.index(f"row.{key}"))
    assert len(headers) == len(positions) == 7
    assert positions == order, positions
