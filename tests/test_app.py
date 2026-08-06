"""Тесты каркаса приложения.

Прогоняются в CI до выката: красные тесты означают, что деплоя не будет.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_which_secrets_arrived(monkeypatch):
    """Флаги ловят потерянный по дороге секрет: без них функция выключается молча."""
    monkeypatch.setenv("ADMIN_PASSWORD", "есть")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "есть")
    monkeypatch.delenv("YANDEX_API_KEY", raising=False)
    health = client.get("/api/health").json()
    assert health["admin"] is True
    assert health["ai"] is True
    assert health["ai_provider"] == "anthropic"

    # Ключи Яндекса перевешивают: запрос уходит с сервера, а он в России.
    monkeypatch.setenv("YANDEX_API_KEY", "есть")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1g...")
    assert client.get("/api/health").json()["ai_provider"] == "yandex"

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("YANDEX_API_KEY", raising=False)
    assert client.get("/api/health").json()["ai"] is False


def test_health_never_leaks_secret_values(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "очень-секретный-пароль")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-секрет")
    body = client.get("/api/health").text
    assert "очень-секретный-пароль" not in body
    assert "sk-ant-секрет" not in body


def test_index_renders_in_russian():
    response = client.get("/")
    assert response.status_code == 200
    assert 'lang="ru"' in response.text
    assert "Дегустация виски" in response.text


def test_index_uses_static_stylesheet():
    # Стили отдаёт Caddy файлом из докрута, а не приложение: если путь разъедется,
    # страница молча станет белой. Проверяем, что ссылка та, которую ждёт Caddy.
    assert '/static/app.css' in client.get("/").text


def test_openapi_is_not_published():
    # Это сайт для гостей, а не публичное API: схема и Swagger отключены.
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert client.get(path).status_code == 404


def test_unknown_page_gives_404():
    assert client.get("/no-such-page").status_code == 404


def test_pages_carry_a_link_preview(client):
    """Ссылку кидают в телеграм — превью не должно быть голым."""
    page = client.get("/whisky").text
    assert 'property="og:title"' in page
    assert "static/preview.png" in page
    assert 'rel="icon"' in page
    assert 'name="theme-color"' in page


def test_description_is_page_specific(client):
    assert "покажем цвет, нос" in client.get("/whisky").text
    assert "два круга" in client.get("/").text


def test_the_home_page_describes_a_working_site(client):
    """Обещать «что появится дальше» на готовом сайте — обманывать гостя."""
    page = client.get("/").text
    assert "появится" not in page
    assert "Как считаются очки" in page
    assert "Открыть поиск" in page


def test_a_broken_link_shows_a_page_not_a_json_dump(client):
    """/whisky/ask открывается ссылкой, а не формой — и это делали.

    Раньше на такой адрес FastAPI отвечал JSON с разбором запроса. Гость
    решает по нему, что сломался весь вечер.
    """
    response = client.get("/whisky/ask", headers={"Accept": "text/html"})
    assert response.status_code == 422
    assert "На главную" in response.text
    assert "detail" not in response.text


def test_json_callers_still_get_json(client):
    response = client.get("/qr.svg")
    assert response.status_code == 422
    assert "detail" in response.json()
