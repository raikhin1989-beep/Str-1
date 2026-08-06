"""Общие настройки шаблонов.

Шаблоны подключают четыре модуля страниц, и до сих пор каждый собирал
окружение Jinja сам. Пока в нём не было ничего своего, это было не важно;
как только появился первый фильтр, оказалось, что добавлять его пришлось бы
в четыре места — и в трёх из них о нём бы забыли.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def plural(number, one: str, few: str, many: str) -> str:
    """«1 балл», «2 балла», «5 баллов» — по правилам русского счёта.

    На странице итогов стояло «Максимум при таком составе — 24 баллов»:
    число там считается из числа образцов, и угадать окончание заранее
    нельзя. При трёх образцах выходит 24, при четырёх 30, при двух 12 —
    и все три требуют разного слова.
    """
    number = abs(int(number))
    if number % 100 // 10 == 1:
        # Одиннадцать–девятнадцать: «11 баллов», а не «11 балл».
        return many
    if number % 10 == 1:
        return one
    if 2 <= number % 10 <= 4:
        return few
    return many


def spaced(number) -> str:
    """12000 → «12 000». Цену читают глазами, а не считают разряды пальцем."""
    try:
        return f"{int(str(number).strip()):,}".replace(",", "\u00a0")
    except (TypeError, ValueError):
        return str(number or "")


def build() -> Jinja2Templates:
    """Окружение шаблонов со всеми нашими фильтрами."""
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters["plural"] = plural
    templates.env.filters["spaced"] = spaced
    return templates
