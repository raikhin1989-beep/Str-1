"""Общая подготовка тестов: своя база на каждый тест, известный пароль."""

import pytest
from fastapi.testclient import TestClient

from app import ai, auth, db, limits, telegram
from app.main import app

TEST_PASSWORD = "тест-пароль-админки"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Каждый тест работает со своей пустой базой во временном каталоге."""
    monkeypatch.setenv("STR1_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADMIN_PASSWORD", TEST_PASSWORD)
    db.reset_schema_cache()
    # Счётчик неудачных входов живёт в памяти процесса — чистим между тестами,
    # иначе блокировка из одного теста утекает в следующий.
    auth._failures.clear()
    limits.reset()
    telegram.forget_username()
    # Права на Vision OCR приложение выясняет у самого Яндекса. В тестах
    # ходить туда нельзя ни при каких обстоятельствах: это чужой сервис,
    # он платный и его может не быть. Заглушка отвечает «не пускают» —
    # тесту, которому нужно обратное, заглушку подменяют своей.
    ai.reset_ocr_cache()
    ai.reset_models_cache()
    monkeypatch.setattr(ai, "_ask_ocr_whether_we_may", lambda: False)
    yield
    ai.reset_ocr_cache()
    db.reset_schema_cache()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin(client):
    """Клиент с выполненным входом в админку."""
    response = client.post("/admin/login", data={"password": TEST_PASSWORD})
    assert response.status_code == 200, "вход должен был пройти"
    return client
