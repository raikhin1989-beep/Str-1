"""Ограничения частоты в условиях настоящего вечера.

Все гости дегустации сидят в одной квартире и выходят в интернет через один
роутер: снаружи это один адрес. Значит счётчик по адресу считает не человека,
а весь стол — и упирается в потолок как раз тогда, когда всё идёт правильно.
Здесь это проверяется на том самом сценарии, из-за которого правило и менялось.
"""

from app import ai, limits, models

ONE_WIFI = {"x-forwarded-for": "95.24.10.7"}


def _open_tasting(guests: int = 0):
    tasting_id = models.create_tasting("Вечер", None, "class")
    for row in models.list_whiskies()[:5]:
        models.add_whisky_to_tasting(tasting_id, row["id"])
    models.set_status(tasting_id, "registration")
    tokens = [models.register_participant(tasting_id, f"Гость {i}") for i in range(guests)]
    return tasting_id, tokens


def test_a_whole_party_can_register_from_one_router(client):
    """Было десять записей на адрес — одиннадцатый гость получал отказ
    на пороге, хотя не сделал ничего плохого."""
    tasting_id, _ = _open_tasting()
    code = models.get_tasting(tasting_id)["public_code"]

    for i in range(25):
        page = client.post(
            f"/join/{code}",
            data={"name": f"Гость {i}", "contact": "@nick"},
            headers=ONE_WIFI,
            follow_redirects=True,
        )
        assert "Слишком много записей" not in page.text, f"гость №{i + 1} не смог записаться"
    assert len(models.list_participants(tasting_id)) == 25


def test_flooding_registration_is_still_stopped(client):
    """Потолок подняли, но не убрали: двести записей за минуту сорвали бы вечер."""
    tasting_id, _ = _open_tasting()
    code = models.get_tasting(tasting_id)["public_code"]

    refused = False
    for i in range(200):
        page = client.post(
            f"/join/{code}", data={"name": f"Бот {i}"}, headers=ONE_WIFI, follow_redirects=True
        )
        if "Слишком много записей" in page.text:
            refused = True
            break
    assert refused, "поток записей должен упираться в потолок"


def test_one_guest_cannot_use_up_everyone_elses_drafts(client):
    """Черновик считается по личной ссылке. Раньше — по адресу, и тот, кто
    печатал заметки усерднее прочих, отключал автосохранение всему столу."""
    tasting_id, tokens = _open_tasting(guests=3)
    models.set_status(tasting_id, "round_nose")
    greedy, quiet = tokens[0], tokens[1]

    limit = limits.LIMITS["draft"][0]
    for _ in range(limit + 5):
        client.post(f"/me/{greedy}/draft", json={"answers": {}, "scores": {}, "tags": {}},
                    headers=ONE_WIFI)

    # Сосед за тем же столом и тем же роутером сохраняется как ни в чём не бывало.
    response = client.post(f"/me/{quiet}/draft", json={"answers": {}, "scores": {}, "tags": {}},
                           headers=ONE_WIFI)
    assert response.status_code == 200, "чужая активность не должна мешать"
    assert response.json()["ok"] is True


def test_a_single_guest_is_still_capped(client):
    tasting_id, tokens = _open_tasting(guests=1)
    models.set_status(tasting_id, "round_nose")
    token = tokens[0]

    codes = set()
    for _ in range(limits.LIMITS["draft"][0] + 5):
        codes.add(
            client.post(f"/me/{token}/draft", json={"answers": {}, "scores": {}, "tags": {}}).status_code
        )
    assert 429 in codes, "свой же черновик перебирать бесконечно нельзя"


def test_the_ai_quota_fits_a_party_not_a_single_person():
    """Двадцать вопросов в час на весь стол — это по два на человека,
    после чего сайт отвечал отказом всем сразу."""
    ai._requests.clear()
    passed = 0
    try:
        while passed < 500:
            ai.check_rate_limit("95.24.10.7")
            passed += 1
    except ai.RateLimited:
        pass
    assert passed >= 50, f"на компанию из десяти человек {passed} вопросов в час мало"
