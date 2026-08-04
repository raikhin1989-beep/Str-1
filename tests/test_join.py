"""Регистрация гостей и привязка телеграма."""

import pytest

from app import join, models, telegram
from tests.conftest import TEST_PASSWORD

# Только латиница, цифры, _ и - : секрет уезжает в HTTP-заголовок, а телеграм
# и сам других символов в нём не принимает.
SECRET = "test-webhook-secret-0123456789"


@pytest.fixture(autouse=True)
def bot(monkeypatch):
    """Бот «настроен», но в сеть не ходит: отправку сообщений подменяем."""
    sent = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:тест")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "raikhinwhiskey_bot")
    monkeypatch.setattr(telegram, "_username", None)
    monkeypatch.setattr(telegram, "send_message", lambda chat_id, text: sent.append((chat_id, text)) or True)
    return sent


def _open_tasting() -> str:
    tasting_id = models.create_tasting("Первая", None, "class")
    models.set_status(tasting_id, "registration")
    return models.get_tasting(tasting_id)["public_code"]


def test_tasting_gets_an_unguessable_code():
    code = models.get_tasting(models.create_tasting("Тест", None, "class"))["public_code"]
    assert code and len(code) >= 10


def test_registration_page_opens_by_code(client):
    response = client.get(f"/join/{_open_tasting()}")
    assert response.status_code == 200
    assert "Записаться" in response.text


def test_unknown_code_gives_404(client):
    assert client.get("/join/такого-нет").status_code == 404


def test_guest_registers_and_lands_on_personal_page(client):
    code = _open_tasting()
    response = client.post(f"/join/{code}", data={"name": "Пётр"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Пётр" in response.text
    assert "Привязать телеграм" in response.text


def test_registration_is_closed_outside_its_stage(client):
    tasting_id = models.create_tasting("Тест", None, "class")
    code = models.get_tasting(tasting_id)["public_code"]
    page = client.get(f"/join/{code}")
    assert "<h2>Записаться</h2>" not in page.text, "формы регистрации быть не должно"
    assert "Записаться нельзя" in page.text
    # И напрямую тоже не проходит.
    response = client.post(f"/join/{code}", data={"name": "Пётр"}, follow_redirects=False)
    assert "error" in response.headers["location"]


def test_name_is_required():
    tasting_id = models.create_tasting("Тест", None, "class")
    models.set_status(tasting_id, "registration")
    with pytest.raises(ValueError):
        models.register_participant(tasting_id, "   ")


def test_start_command_links_the_account(client, bot):
    code = _open_tasting()
    client.post(f"/join/{code}", data={"name": "Пётр"}, follow_redirects=True)
    token = models.list_participants(models.get_tasting_by_code(code)["id"])[0]["join_token"]

    response = client.post(
        f"/tg/{SECRET}",
        json={"message": {"chat": {"id": 555}, "from": {"username": "petya"}, "text": f"/start {token}"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 200

    participant = models.get_participant_by_token(token)
    assert participant["tg_chat_id"] == 555
    assert participant["tg_username"] == "petya"
    assert bot and "Готово, Пётр" in bot[0][1]

    # На личной странице видно, что всё привязалось.
    assert "Телеграм привязан" in client.get(f"/me/{token}").text


def test_webhook_rejects_wrong_secret_in_header(client):
    response = client.post(
        f"/tg/{SECRET}",
        json={"message": {"chat": {"id": 1}, "text": "/start любой"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "someone-elses-secret"},
    )
    assert response.status_code == 404


def test_webhook_rejects_wrong_secret_in_path(client):
    response = client.post(
        "/tg/чужой-путь",
        json={"message": {"chat": {"id": 1}, "text": "/start любой"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 404


def test_unknown_token_does_not_link_anyone(client, bot):
    response = client.post(
        f"/tg/{SECRET}",
        json={"message": {"chat": {"id": 777}, "text": "/start выдуманный-токен"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 200
    assert "Не нашёл" in bot[0][1]


def test_plain_message_is_ignored(client, bot):
    response = client.post(
        f"/tg/{SECRET}",
        json={"message": {"chat": {"id": 1}, "text": "привет"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 200
    assert bot == []


def test_start_without_token_is_ignored():
    assert telegram.parse_start_command({"message": {"chat": {"id": 1}, "text": "/start"}}) is None


def test_qr_returns_svg(client):
    response = client.get("/qr.svg", params={"data": "https://example.org/join/abc"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in response.content


def test_admin_sees_the_link_and_the_guest_list(client):
    code = _open_tasting()
    client.post(f"/join/{code}", data={"name": "Пётр"}, follow_redirects=True)
    client.post("/admin/login", data={"password": TEST_PASSWORD})
    tasting_id = models.get_tasting_by_code(code)["id"]
    page = client.get(f"/admin/tastings/{tasting_id}").text
    assert f"/join/{code}" in page
    assert "Пётр" in page
    assert "qr.svg" in page


def test_personal_page_of_a_stranger_is_404(client):
    assert client.get("/me/чужой-токен").status_code == 404


def test_qr_is_black_on_white_with_a_quiet_zone(client):
    """Код сканируют с чужого экрана: фон должен быть в самой картинке."""
    svg = client.get("/qr.svg", params={"data": "https://example.org/join/abc"}).text
    assert 'fill="white"' in svg, "прозрачный фон на тёмной теме нечитаем"
    # Поле в 4 модуля по спецификации: с меньшим часть телефонов не ловит код.
    assert svg.count("M4,4H5V5H4z") or "M4,4" in svg


def test_guest_links_use_the_public_address(admin, monkeypatch):
    """Админку открывают и по запасному входу — гостю нужен домен."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://raikhinwhiskey.duckdns.org")
    tasting_id = models.create_tasting("Первая", None, "class")
    page = admin.get(f"/admin/tastings/{tasting_id}").text
    assert "https://raikhinwhiskey.duckdns.org/join/" in page
    assert "testserver/join/" not in page


def test_without_the_public_address_links_fall_back_to_the_current_one(admin, monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    tasting_id = models.create_tasting("Первая", None, "class")
    page = admin.get(f"/admin/tastings/{tasting_id}").text
    assert "http://testserver/join/" in page


def test_start_without_a_code_is_logged_as_a_miss(client, bot):
    """Самая частая причина «не привязалось»: человек написал боту сам."""
    from app.db import connect

    response = client.post(
        f"/tg/{SECRET}",
        json={"message": {"chat": {"id": 555}, "text": "/start"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 200
    with connect() as conn:
        row = conn.execute(
            "SELECT action, details FROM audit_log WHERE action LIKE 'tg.%' ORDER BY id DESC"
        ).fetchone()
    assert row["action"] == "tg.мимо"
    assert row["details"] == "Старт без кода"


def test_a_successful_link_is_logged_too(client, bot):
    from app.db import connect

    code = _open_tasting()
    token = client.post(
        f"/join/{code}", data={"name": "Саша"}, follow_redirects=False
    ).headers["location"].removeprefix("/me/")

    client.post(
        f"/tg/{SECRET}",
        json={"message": {"chat": {"id": 555}, "text": f"/start {token}",
                          "from": {"username": "sasha"}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    with connect() as conn:
        row = conn.execute(
            "SELECT action, details FROM audit_log WHERE action LIKE 'tg.%' ORDER BY id DESC"
        ).fetchone()
    assert row["action"] == "tg.привязка"
    assert "Саша" in row["details"] and "@sasha" in row["details"]


def test_a_stale_code_is_logged_as_a_stranger(client, bot):
    from app.db import connect

    client.post(
        f"/tg/{SECRET}",
        json={"message": {"chat": {"id": 555}, "text": "/start кода-такого-нет"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    with connect() as conn:
        row = conn.execute(
            "SELECT action FROM audit_log WHERE action LIKE 'tg.%' ORDER BY id DESC"
        ).fetchone()
    assert row["action"] == "tg.чужой код"


def test_the_admin_page_shows_what_arrived(admin, client, bot):
    client.post(
        f"/tg/{SECRET}",
        json={"message": {"chat": {"id": 555}, "text": "/start"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    page = admin.get("/admin/telegram").text
    assert "Старт без кода" in page
    assert "raikhinwhiskey_bot" in page
    assert "Как это читать" in page


def test_the_guest_page_warns_against_writing_to_the_bot_directly(client, bot):
    code = _open_tasting()
    token = client.post(
        f"/join/{code}", data={"name": "Саша"}, follow_redirects=False
    ).headers["location"].removeprefix("/me/")
    page = client.get(f"/me/{token}").text
    assert "Открывайте именно эту" in page
    assert "не сработает" in page


def test_after_the_evening_the_join_link_shows_the_results(client, bot):
    """По старому QR приходят и назавтра — тупик «регистрация закрыта» не годится."""
    tasting_id = models.create_tasting("Прошлый вечер", None, "class")
    for name in ("Ardbeg 10", "Talisker 10", "Oban 14"):
        models.add_whisky_to_tasting(tasting_id, models.save_whisky({"name": name}))
    models.set_status(tasting_id, "registration")
    token = models.register_participant(tasting_id, "Саша")
    person = models.get_participant_by_token(token)["id"]
    models.set_status(tasting_id, "round_nose")
    models.save_round_draft(person, "nose", dict(models.tasting_truth(tasting_id)))
    models.set_status(tasting_id, "round_palate")
    models.set_status(tasting_id, "scoring")
    models.compute_results(tasting_id)
    models.set_status(tasting_id, "closed")

    code = models.get_tasting(tasting_id)["public_code"]
    page = client.get(f"/join/{code}").text
    assert "Дегустация окончена" in page
    assert "Победил" in page and "Саша" in page
    assert f"/results/{code}" in page
    assert "<h2>Записаться</h2>" not in page


def test_a_round_in_progress_points_the_guest_at_their_own_page(client, bot):
    code = _open_tasting()
    token = client.post(
        f"/join/{code}", data={"name": "Саша"}, follow_redirects=False
    ).headers["location"].removeprefix("/me/")
    models.set_status(models.get_tasting_by_code(code)["id"], "round_nose")

    page = client.get(f"/join/{code}").text
    assert "Уже начали" in page
    assert f"/me/{token}" in page, "телефон помнит гостя — ведём его к себе"
