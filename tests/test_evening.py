"""Весь вечер целиком, от создания дегустации до рассылки итогов.

Каждый кусок проверен своим набором тестов; этот — про то, что они стыкуются.
Ломается он обычно не от ошибки в логике, а от несовпадения ожиданий на стыке:
имя поля в форме, статус, порядок переходов. Такое ловится только сквозным
прогоном.

Всё делается ровно так, как будет вечером: админ — через страницы админки,
гости — через публичные формы, ничего не вызывается напрямую в обход HTTP.
"""

import pytest
from markupsafe import escape

from app import models, telegram

SAMPLES = 3


def _lineup():
    """Три позиции из справочника — он уже заполнен миграцией, как и на сервере."""
    return models.list_whiskies()[:SAMPLES]


@pytest.fixture
def bot(monkeypatch):
    box = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:тест")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret-0123456789")
    monkeypatch.setattr(
        telegram, "send_message", lambda chat_id, text: box.append((chat_id, text)) or True
    )
    return box


def test_a_whole_evening(admin, client, bot):
    # 1. Админ добавляет виски в справочник и заводит дегустацию. Справочник
    # уже не пуст: пять бутылок первой дегустации завела миграция.
    admin.post(
        "/admin/whiskies",
        data={"name": "Ardbeg 10", "wclass": "односолодовый скотч"},
        follow_redirects=True,
    )
    assert any(row["name"] == "Ardbeg 10" for row in models.list_whiskies())

    admin.post(
        "/admin/tastings",
        data={"title": "Первая", "held_on": "", "category_level": "class"},
        follow_redirects=True,
    )
    tasting_id = models.list_tastings()[0]["id"]

    for whisky in _lineup():
        admin.post(
            f"/admin/tastings/{tasting_id}/samples",
            data={"whisky_id": whisky["id"]},
            follow_redirects=True,
        )
    admin.post(f"/admin/tastings/{tasting_id}/shuffle", follow_redirects=True)
    assert len(models.tasting_whiskies(tasting_id)) == SAMPLES

    # 2. Открывается регистрация, гости записываются по публичной ссылке.
    admin.post(
        f"/admin/tastings/{tasting_id}/status",
        data={"status": "registration"},
        follow_redirects=True,
    )
    code = models.get_tasting(tasting_id)["public_code"]

    tokens = {}
    for name in ("Саша", "Женя"):
        response = client.post(f"/join/{code}", data={"name": name}, follow_redirects=False)
        tokens[name] = response.headers["location"].removeprefix("/me/")
    models.link_telegram(tokens["Саша"], 111, "sasha")

    # 3. Раунд по запаху. Саша расставляет верно, Женя — наоборот.
    admin.post(
        f"/admin/tastings/{tasting_id}/status",
        data={"status": "round_nose"},
        follow_redirects=True,
    )
    truth = models.tasting_truth(tasting_id)
    reversed_answer = dict(zip(sorted(truth), reversed([truth[no] for no in sorted(truth)])))

    page = client.get(f"/me/{tokens['Саша']}").text
    assert "Раунд по запаху" in page

    client.post(
        f"/me/{tokens['Саша']}/submit",
        data={f"sample_{no}": str(wid) for no, wid in truth.items()},
        follow_redirects=True,
    )
    # Женя только сохраняет черновик и кнопку не нажимает — обычное дело.
    client.post(
        f"/me/{tokens['Женя']}/draft",
        json={"answers": {str(no): str(wid) for no, wid in reversed_answer.items()},
              "scores": {"1": "80"}},
    )

    admin_page = admin.get(f"/admin/tastings/{tasting_id}").text
    assert "1 из 2" in admin_page

    # 4. Раунд по вкусу. Закрытие первого замораживает Женин черновик.
    admin.post(
        f"/admin/tastings/{tasting_id}/status",
        data={"status": "round_palate"},
        follow_redirects=True,
    )
    zhenya = models.get_participant_by_token(tokens["Женя"])["id"]
    assert models.round_submitted(zhenya, "nose"), "черновик должен был засчитаться"

    page = client.get(f"/me/{tokens['Саша']}").text
    assert "Раунд по вкусу" in page
    assert "selected" not in page, "ответы первого раунда не подсказываются"

    for name, answer in (("Саша", truth), ("Женя", truth)):
        client.post(
            f"/me/{tokens[name]}/submit",
            data={f"sample_{no}": str(wid) for no, wid in answer.items()}
            | {f"score_{no}": "70" for no in truth},
            follow_redirects=True,
        )

    # 5. Итоги.
    admin.post(
        f"/admin/tastings/{tasting_id}/status",
        data={"status": "scoring"},
        follow_redirects=True,
    )
    board = models.leaderboard(tasting_id)
    assert [row["name"] for row in board] == ["Саша", "Женя"]
    assert board[0]["place"] == 1 and board[0]["total"] > board[1]["total"]

    results = client.get(f"/results/{code}").text
    assert "Турнирная таблица" in results
    # Через escape: какой виски окажется первым, решает перемешивание, а в
    # «Jack Daniel's» апостроф на странице выглядит как &#39;.
    poured = models.tasting_whiskies(tasting_id)[0]["name"]
    assert str(escape(poured)) in results, "теперь состав раскрыт"

    live = client.get(f"/api/board/{code}").json()
    assert live["rows"][0]["name"] == "Саша"

    personal = client.get(f"/me/{tokens['Женя']}").text
    assert "Ваш результат" in personal

    # 6. Рассылка: уходит только привязанному, повтор ничего не дублирует.
    admin.post(f"/admin/tastings/{tasting_id}/broadcast", follow_redirects=True)
    assert [chat_id for chat_id, _ in bot] == [111]
    admin.post(f"/admin/tastings/{tasting_id}/broadcast", follow_redirects=True)
    assert len(bot) == 1

    # 7. И бэкап на память о вечере.
    assert admin.get("/admin/backup").content.startswith(b"SQLite format 3")


def test_the_pouring_stays_secret_until_the_end(admin, client):
    """Главное свойство вечера: до итогов никто не должен узнать, что налито."""
    admin.post(
        "/admin/tastings",
        data={"title": "Первая", "held_on": "", "category_level": "class"},
        follow_redirects=True,
    )
    tasting_id = models.list_tastings()[0]["id"]
    for whisky in _lineup():
        admin.post(
            f"/admin/tastings/{tasting_id}/samples",
            data={"whisky_id": whisky["id"]},
            follow_redirects=True,
        )
    admin.post(
        f"/admin/tastings/{tasting_id}/status", data={"status": "registration"}, follow_redirects=True
    )
    code = models.get_tasting(tasting_id)["public_code"]
    token = client.post(
        f"/join/{code}", data={"name": "Гость"}, follow_redirects=False
    ).headers["location"].removeprefix("/me/")
    admin.post(
        f"/admin/tastings/{tasting_id}/status", data={"status": "round_nose"}, follow_redirects=True
    )

    truth = models.tasting_truth(tasting_id)
    names = [row["name"] for row in models.tasting_whiskies(tasting_id)]
    page = client.get(f"/me/{token}").text

    # Ни один вариант не выбран заранее и не помечен — иначе страница сама
    # выдавала бы ответ.
    assert "selected" not in page

    # Каждое название встречается ровно столько раз, сколько образцов: список
    # у всех номеров один и тот же, и по нему ничего не вычислить.
    for name in names:
        # Сравниваем с экранированным видом: в «Jack Daniel's» апостроф
        # на странице выглядит как &#39;.
        assert page.count(str(escape(name))) == len(truth), (
            f"{name}: список должен быть одинаковым"
        )

    # А до подведения итогов страница итогов не показывает состав вовсе.
    results = client.get(f"/results/{code}").text
    assert all(str(escape(name)) not in results for name in names)
