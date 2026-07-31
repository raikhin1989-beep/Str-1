"""Общая подготовка тестов: своя база на каждый тест, известный пароль."""

import pytest
from fastapi.testclient import TestClient

from app import auth, db
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
    yield
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
