"""Тесты каркаса приложения.

Прогоняются в CI до выката: красные тесты означают, что деплоя не будет.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
