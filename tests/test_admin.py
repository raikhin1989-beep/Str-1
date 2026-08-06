"""Вход в админку, защита от перебора пароля и правка справочника."""

from app import auth, models
from tests.conftest import TEST_PASSWORD


def test_admin_requires_login(client):
    # follow_redirects=False, иначе не увидеть сам факт переадресации.
    response = client.get("/admin/tastings", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_login_with_wrong_password_fails(client):
    response = client.post("/admin/login", data={"password": "не тот"})
    assert response.status_code == 401
    assert auth.COOKIE_NAME not in response.cookies


def test_login_with_right_password_opens_admin(client):
    response = client.post("/admin/login", data={"password": TEST_PASSWORD})
    assert response.status_code == 200
    assert "Дегустации" in response.text
    assert client.cookies.get(auth.COOKIE_NAME)


def test_logout_closes_access(admin):
    admin.post("/admin/logout")
    response = admin.get("/admin/tastings", follow_redirects=False)
    assert response.status_code == 303


def test_lockout_after_repeated_failures(client):
    for _ in range(auth.MAX_ATTEMPTS):
        client.post("/admin/login", data={"password": "не тот"})
    # Даже верный пароль теперь не проходит: адрес заперт.
    response = client.post("/admin/login", data={"password": TEST_PASSWORD})
    assert response.status_code == 429
    assert "попыток" in response.text


def test_admin_disabled_without_password(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    response = client.get("/admin/login")
    assert response.status_code == 503
    assert "ADMIN_PASSWORD" in response.text


def test_session_cookie_is_httponly(client):
    # Без follow_redirects=False смотрели бы на заголовки уже следующей
    # страницы, где никакой куки не выставляется.
    response = client.post(
        "/admin/login", data={"password": TEST_PASSWORD}, follow_redirects=False
    )
    cookie_header = response.headers.get("set-cookie", "")
    assert "httponly" in cookie_header.lower()
    assert "samesite=strict" in cookie_header.lower()


def test_a_whisky_can_be_deleted(admin):
    whisky_id = models.save_whisky({"name": "Лишняя запись", "wclass": "прочее"})
    response = admin.post(f"/admin/whiskies/{whisky_id}/delete")
    assert response.status_code == 200
    assert "Удалено" in response.text
    assert models.get_whisky(whisky_id) is None


def test_a_poured_whisky_cannot_be_deleted(admin):
    """Состав и ответы на него ссылаются, а прошлый вечер должен остаться
    читаемым: итоги считаются из ответов заново."""
    tasting_id = models.create_tasting("Вечер с составом", None, "class")
    whisky_id = models.save_whisky({"name": "Налитый", "wclass": "прочее"})
    models.add_whisky_to_tasting(tasting_id, whisky_id)

    response = admin.post(f"/admin/whiskies/{whisky_id}/delete")
    assert models.get_whisky(whisky_id) is not None, "запись должна была уцелеть"
    assert "Вечер с составом" in response.text, "надо назвать причину, а не просто отказать"


def test_a_whisky_named_in_an_answer_cannot_be_deleted(admin):
    """Из состава убрали, а в чьём-то ответе он остался — тогда в разборе
    ответов на месте названия была бы дырка."""
    tasting_id = models.create_tasting("Вечер с ответом", None, "class")
    poured = models.save_whisky({"name": "Налитый", "wclass": "прочее"})
    guessed = models.save_whisky({"name": "Названный", "wclass": "прочее"})
    models.add_whisky_to_tasting(tasting_id, poured)
    models.set_status(tasting_id, "registration")
    token = models.register_participant(tasting_id, "Гость")
    person = models.get_participant_by_token(token)["id"]
    models.set_status(tasting_id, "round_nose")
    models.save_round_draft(person, "nose", {1: guessed}, {}, {})

    admin.post(f"/admin/whiskies/{guessed}/delete")
    assert models.get_whisky(guessed) is not None
    assert models.whisky_usage(guessed) == ["Вечер с ответом"]


def test_deleting_something_that_is_gone_is_a_404(admin):
    assert admin.post("/admin/whiskies/999999/delete").status_code == 404


def test_the_delete_button_is_hidden_when_it_would_fail(admin):
    """Причину показываем заранее, а не после нажатия."""
    tasting_id = models.create_tasting("Занятый вечер", None, "class")
    whisky_id = models.save_whisky({"name": "Налитый", "wclass": "прочее"})
    models.add_whisky_to_tasting(tasting_id, whisky_id)

    page = admin.get(f"/admin/whiskies/{whisky_id}").text
    assert "Занятый вечер" in page
    assert "/delete" not in page

    free = models.save_whisky({"name": "Свободный", "wclass": "прочее"})
    assert f"/admin/whiskies/{free}/delete" in admin.get(f"/admin/whiskies/{free}").text


def test_the_catalogue_can_be_searched_in_the_admin(admin):
    """Полторы сотни строк одной таблицей — не для правки."""
    models.save_whisky({"name": "Ardbeg 10", "region": "Islay"})
    models.save_whisky({"name": "Jim Beam", "region": "Kentucky"})

    found = admin.get("/admin/whiskies", params={"q": "islay"}).text
    assert "Ardbeg 10" in found
    assert "Jim Beam" not in found


def test_the_search_comes_before_the_add_form(admin):
    """Искать и править приходится каждый вечер, заводить новое — редко."""
    page = admin.get("/admin/whiskies").text
    assert page.index("Поиск по справочнику") < page.index("Добавить виски")



def test_the_admin_sees_who_answered_each_round(admin):
    """Счётчик «сдали N из M» показывает только идущий раунд и исчезает вместе
    с ним. После вечера было не понять, сдал ли человек вкус, — спросили на
    живой дегустации."""
    tasting_id = models.create_tasting("Вечер", None, "class")
    for row in models.list_whiskies()[:3]:
        models.add_whisky_to_tasting(tasting_id, row["id"])
    models.set_status(tasting_id, "registration")
    sent = models.register_participant(tasting_id, "Ответивший")
    draft = models.register_participant(tasting_id, "Черновик")
    models.register_participant(tasting_id, "Молчун")
    models.set_status(tasting_id, "round_nose")

    truth = models.tasting_truth(tasting_id)
    for token, submit in ((sent, True), (draft, False)):
        person = models.get_participant_by_token(token)["id"]
        models.save_round_draft(person, "nose", dict(truth), {}, {})
        if submit:
            models.submit_round(person, "nose")

    status = models.answer_status(tasting_id)
    people = {p["name"]: p["id"] for p in models.list_participants(tasting_id)}
    assert status[people["Ответивший"]]["nose"] == "отправлен"
    assert status[people["Черновик"]]["nose"] == "черновик"
    assert status.get(people["Молчун"], {}).get("nose") is None

    # И это видно на странице — в том числе когда раунды уже кончились.
    models.set_status(tasting_id, "round_palate")
    models.set_status(tasting_id, "scoring")
    page = admin.get(f"/admin/tastings/{tasting_id}").text
    assert "отправлен" in page
    assert "черновик" in page


def test_the_host_can_add_a_latecomer_after_the_rounds_start(admin, client):
    """Публичная запись закрыта с началом раундов, а опоздавший — правило."""
    tasting_id = models.create_tasting("Первая", None, "class")
    for name in ("A", "B", "C"):
        models.add_whisky_to_tasting(tasting_id, models.save_whisky({"name": name}))
    models.set_status(tasting_id, "registration")
    code = models.get_tasting(tasting_id)["public_code"]
    models.set_status(tasting_id, "round_nose")

    # По ссылке — уже нельзя, и это правильно: случайный человек не должен
    # вписаться в идущую дегустацию.
    refused = client.post(f"/join/{code}", data={"name": "Мимо"}, follow_redirects=True)
    assert "закрыта" in refused.text
    assert models.list_participants(tasting_id) == []

    page = admin.post(
        f"/admin/tastings/{tasting_id}/participants",
        data={"name": "Опоздавший", "contact": "@late"},
        follow_redirects=True,
    ).text
    assert "Гость записан" in page
    people = models.list_participants(tasting_id)
    assert [p["name"] for p in people] == ["Опоздавший"]

    # И раунд ему доступен сразу — иначе запись бессмысленна.
    token = people[0]["join_token"]
    assert "Раунд по запаху" in client.get(f"/me/{token}").text


def test_nobody_is_added_to_a_finished_tasting(admin):
    """Запись после итогов — это участник с нулём и без единого раунда."""
    tasting_id = models.create_tasting("Первая", None, "class")
    models.add_whisky_to_tasting(tasting_id, models.save_whisky({"name": "A"}))
    for status in ("registration", "round_nose", "round_palate", "scoring"):
        models.set_status(tasting_id, status)
    page = admin.post(
        f"/admin/tastings/{tasting_id}/participants",
        data={"name": "Поздний"},
        follow_redirects=True,
    ).text
    assert "закончена" in page
    assert models.list_participants(tasting_id) == []
