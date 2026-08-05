"""Эксплуатация: бэкапы, страницы ошибок, ограничение частоты, журнал."""

import gzip
import sqlite3

import pytest

from app import backup, limits, models


def test_snapshot_is_a_working_database(tmp_path):
    """Копия должна открываться и содержать данные, а не быть пустым файлом."""
    models.save_whisky({"name": "Ardbeg 10"})
    target = tmp_path / "copy.db"
    backup.snapshot(target)

    conn = sqlite3.connect(target)
    names = [row[0] for row in conn.execute("SELECT name FROM whisky")]
    conn.close()
    assert "Ardbeg 10" in names


def test_snapshot_catches_writes_still_in_the_wal(tmp_path):
    """Файл базы копировать нельзя: в режиме WAL свежие записи лежат отдельно."""
    models.save_whisky({"name": "Только что записан"})
    target = tmp_path / "copy.db"
    backup.snapshot(target)

    conn = sqlite3.connect(target)
    found = conn.execute(
        "SELECT COUNT(*) FROM whisky WHERE name = ?", ("Только что записан",)
    ).fetchone()[0]
    conn.close()
    assert found == 1


def test_daily_backup_is_compressed_and_readable(tmp_path):
    models.save_whisky({"name": "Talisker 10"})
    archive = backup.daily(tmp_path, keep=14)
    assert archive.suffixes[-1] == ".gz"

    restored = tmp_path / "restored.db"
    with gzip.open(archive, "rb") as source:
        restored.write_bytes(source.read())
    conn = sqlite3.connect(restored)
    names = [row[0] for row in conn.execute("SELECT name FROM whisky")]
    conn.close()
    assert "Talisker 10" in names


def test_only_the_last_copies_are_kept(tmp_path):
    for index in range(20):
        (tmp_path / f"app-2026073{index:02d}-000000.db.gz").write_bytes(b"x")
    backup.prune(tmp_path, keep=14)
    assert len(list(tmp_path.glob("app-*.db.gz"))) == 14


def test_admin_can_download_a_backup(admin):
    models.save_whisky({"name": "Oban 14"})
    response = admin.get("/admin/backup")
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.content[:16].startswith(b"SQLite format 3")


def test_backup_needs_a_login(client):
    response = client.get("/admin/backup", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


# ── страницы ошибок ────────────────────────────────────────────────────────


def test_a_missing_page_is_human_readable(client):
    response = client.get("/такого-нет", headers={"accept": "text/html"})
    assert response.status_code == 404
    assert "Такой страницы нет" in response.text
    assert "На главную" in response.text


def test_machines_still_get_json(client):
    response = client.get("/такого-нет", headers={"accept": "application/json"})
    assert response.status_code == 404
    assert response.json()["detail"]


def test_redirects_are_not_turned_into_error_pages(client):
    """Админка отправляет на форму входа исключением — это не ошибка."""
    response = client.get("/admin/tastings", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


# ── ограничение частоты ────────────────────────────────────────────────────


def test_registration_is_rate_limited(client):
    tasting_id = models.create_tasting("Первая", None, "class")
    models.set_status(tasting_id, "registration")
    code = models.get_tasting(tasting_id)["public_code"]

    limit = limits.LIMITS["join"][0]
    for index in range(limit):
        client.post(f"/join/{code}", data={"name": f"Гость {index}"}, follow_redirects=False)
    response = client.post(f"/join/{code}", data={"name": "Лишний"}, follow_redirects=True)
    assert "Слишком много записей" in response.text
    assert len(models.list_participants(tasting_id)) == limit


def test_the_limit_forgets_after_the_window(monkeypatch):
    limits.check("join", "1.2.3.4")
    monkeypatch.setattr(limits.time, "time", lambda: 9_999_999_999)
    limits.check("join", "1.2.3.4")  # окно прошло — счётчик пуст


def test_draft_autosave_has_its_own_generous_limit():
    """Черновик сохраняется раз в пару секунд — лимит не должен мешать раунду."""
    saves, window = limits.LIMITS["draft"]
    assert saves / window >= 0.3, "меньше — и обычная расстановка упрётся в лимит"


# ── журнал ─────────────────────────────────────────────────────────────────


def test_admin_actions_are_logged(admin):
    from app.db import connect

    tasting_id = models.create_tasting("Первая", None, "class")
    admin.post(
        f"/admin/tastings/{tasting_id}/status",
        data={"status": "registration"},
        follow_redirects=True,
    )
    with connect() as conn:
        actions = [row["action"] for row in conn.execute("SELECT action FROM audit_log")]
    assert "tasting.status" in actions
    assert "admin.login" in actions


def test_english_boilerplate_does_not_reach_the_guest(client):
    """«Not Found» гостю ничего не объясняет — показываем свой текст."""
    page = client.get("/такого-нет", headers={"accept": "text/html"}).text
    assert "Not Found" not in page
    assert "Проверьте ссылку" in page


def test_our_own_message_is_kept(client):
    """А наши собственные пояснения, наоборот, доходят как есть."""
    page = client.get("/me/такого-токена-нет", headers={"accept": "text/html"}).text
    assert "Участник не найден" in page


# ── сбои видно без SSH ─────────────────────────────────────────────────────


def test_a_crash_is_recorded_where_the_host_can_see_it(admin):
    """Живой тест показал «Internal Server Error», и узнать, что именно упало,
    было неоткуда: трасса лежит в журнале службы, до которого посреди вечера
    с телефона не добраться."""
    from app import errors

    # Настоящее исключение, а не собранное руками: смысл записи — в том,
    # где именно всё случилось, а трасса появляется только у брошенного.
    try:
        int([1])
    except TypeError as err:
        errors.remember("/me/abc/draft", err)

    page = admin.get("/admin/errors").text
    assert "TypeError" in page
    assert "/me/abc/draft" in page
    assert "test_ops.py" in page, "должно быть видно место в коде"


def test_recording_a_crash_never_crashes(monkeypatch):
    """Обработчик ошибок — последнее место, где можно падать."""
    from app import errors

    monkeypatch.setattr(errors, "connect", lambda: 1 / 0)
    errors.remember("/", ValueError("что угодно"))  # не должно бросить


def test_the_errors_page_is_behind_the_login(client):
    response = client.get("/admin/errors", follow_redirects=False)
    assert response.status_code == 303


def test_the_host_can_clear_the_list(admin):
    from app import errors

    errors.remember("/", ValueError("раз"))
    assert errors.recent()
    admin.post("/admin/errors/clear")
    assert errors.recent() == []


def test_ordinary_refusals_are_not_recorded_as_crashes(client, admin):
    """404 и «раунд не идёт» — обычные ответы, а не сбои. Иначе список
    заполнится шумом, и настоящую поломку в нём будет не найти."""
    from app import errors

    client.get("/me/чужой-токен")
    client.get("/join/такого-нет")
    assert errors.recent() == []


# ── соединения с базой не должны копиться ──────────────────────────────────


def test_a_request_does_not_leak_a_database_connection(client):
    """Ровно то, что положило сайт 5 августа.

    `with sqlite3.connect(...)` фиксирует транзакцию, но соединение
    оставляет открытым — закрыть его должен сборщик мусора. Пока запросов
    мало, это незаметно; когда за столом несколько телефонов опрашивают
    сервер раз в три секунды, дескрипторы копятся быстрее, чем убираются.
    Кончилось тем, что процесс не мог открыть уже ничего: ни базу
    (`unable to open database file`), ни сокет, ни даже шаблон страницы
    ошибки — и вместо неё отдавалось голое «Internal Server Error».
    """
    import os

    from app import models

    def open_files() -> int:
        return len(os.listdir("/proc/self/fd"))

    models.list_whiskies()          # схема накатана, кэши прогреты
    before = open_files()
    for _ in range(200):
        models.list_whiskies()
    assert open_files() <= before + 5, "соединения не закрываются"


def test_a_failing_query_does_not_leak_either(client):
    """Исключение держит кадр стека, а кадр — соединение. Раньше это
    раскручивало поломку: чем хуже становилось, тем быстрее текло."""
    import os
    import sqlite3

    from app.db import connect

    def open_files() -> int:
        return len(os.listdir("/proc/self/fd"))

    before = open_files()
    kept = []
    for _ in range(200):
        try:
            with connect() as conn:
                conn.execute("SELECT * FROM no_such_table")
        except sqlite3.Error as err:
            kept.append(err)        # держим исключение, как это делает трасса
    assert open_files() <= before + 5, "упавший запрос не закрывает соединение"


def test_migrations_still_run_on_one_connection(tmp_path, monkeypatch):
    """Закрытие по `with` не должно ломать накатывание схемы: там одно
    соединение живёт через несколько `with` подряд, по одному на миграцию."""
    from app import db, models

    monkeypatch.setenv("STR1_DB_PATH", str(tmp_path / "fresh.db"))
    db.reset_schema_cache()
    assert len(models.list_whiskies()) > 100, "справочник должен накатиться целиком"
