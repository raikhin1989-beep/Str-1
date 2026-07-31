"""Вход в админку и защита от перебора пароля."""

from app import auth
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
