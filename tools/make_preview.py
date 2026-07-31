#!/usr/bin/env python3
"""Картинка превью ссылки (Open Graph) — генерируется, а не рисуется руками.

Зачем скрипт, а не просто файл в репозитории: когда понадобится поменять цвет
или размер, не придётся искать, чем это было сделано. Запуск:

    python3 tools/make_preview.py

Пишет site/static/preview.png. Никаких зависимостей: PNG собирается из zlib
и struct вручную, поэтому ни Pillow, ни ImageMagick на машине не нужны.

Текста на картинке нет намеренно. Шрифты пришлось бы либо тащить в репозиторий,
либо растеризовать сторонним пакетом; телеграм и так показывает рядом заголовок
и описание из og:title и og:description, а картинка нужна как фон настроения.
"""

import math
import pathlib
import struct
import zlib

WIDTH, HEIGHT = 1200, 630
OUT = pathlib.Path(__file__).resolve().parent.parent / "site" / "static" / "preview.png"

# Те же цвета, что в site/static/app.css.
BG = (0x10, 0x0E, 0x0C)
GLOW = (0x2A, 0x20, 0x18)
AMBER = (0xD7, 0xA1, 0x54)
AMBER_DEEP = (0x8A, 0x5C, 0x28)


def mix(first, second, weight):
    """Смешать цвета: weight=0 — первый, weight=1 — второй."""
    weight = max(0.0, min(1.0, weight))
    return tuple(round(a + (b - a) * weight) for a, b in zip(first, second))


# Стакан: центр, полуширина сверху, полувысота, радиус скругления дна.
GLASS = {"cx": WIDTH * 0.70, "cy": HEIGHT * 0.52, "hw": 150.0, "hh": 175.0, "r": 46.0}
FILL_LEVEL = 0.52   # доля высоты стакана снизу, занятая напитком
GLASS_EDGE = (0xE8, 0xD5, 0xB5)


def inside_glass(x, y):
    """Внутри ли точка силуэта стакана. Стенки слегка сходятся книзу."""
    top = GLASS["cy"] - GLASS["hh"]
    bottom = GLASS["cy"] + GLASS["hh"]
    if not (top <= y <= bottom):
        return False
    taper = 1 - 0.12 * (y - top) / (2 * GLASS["hh"])
    half = GLASS["hw"] * taper
    dx = abs(x - GLASS["cx"])
    if dx > half:
        return False
    # Скруглённое дно: у самого низа угол срезается окружностью.
    corner_y = bottom - GLASS["r"]
    if y > corner_y and dx > half - GLASS["r"]:
        return math.hypot(dx - (half - GLASS["r"]), y - corner_y) <= GLASS["r"]
    return True


def sample(x, y):
    """Цвет одной точки без сглаживания — сглаживание делает main()."""
    # Тёплое свечение сверху по центру — то же, что радиальный градиент фона.
    dx = (x - WIDTH / 2) / (WIDTH * 0.75)
    dy = (y + HEIGHT * 0.35) / (HEIGHT * 1.25)
    colour = mix(GLOW, BG, math.sqrt(dx * dx + dy * dy) * 1.35)

    top = GLASS["cy"] - GLASS["hh"]
    bottom = GLASS["cy"] + GLASS["hh"]
    surface = bottom - 2 * GLASS["hh"] * FILL_LEVEL

    if inside_glass(x, y):
        if y >= surface:
            # Напиток: у дна темнее, у поверхности светлее.
            depth = (y - surface) / max(1.0, bottom - surface)
            colour = mix(AMBER, AMBER_DEEP, depth ** 1.3)
            # Полоса света у поверхности — то, из-за чего виски выглядит виски.
            colour = mix(colour, (255, 238, 210), max(0.0, 1 - (y - surface) / 26) * 0.5)
            # Блик по левой стенке.
            glare = max(0.0, 1 - abs(x - (GLASS["cx"] - GLASS["hw"] * 0.55)) / 26)
            colour = mix(colour, (255, 245, 225), glare * 0.35)
        else:
            # Пустая часть стакана: чуть светлее фона, как настоящее стекло.
            colour = mix(colour, GLASS_EDGE, 0.06)

    # Кромка стекла: точка у границы силуэта.
    if not inside_glass(x, y):
        near = any(
            inside_glass(x + ox, y + oy)
            for ox, oy in ((-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3))
        )
        if near and top - 4 <= y <= bottom + 4:
            colour = mix(colour, GLASS_EDGE, 0.75)

    # Янтарная черта слева — та же роль, что у заголовка на сайте.
    if 90 <= x <= 96 and HEIGHT * 0.34 <= y <= HEIGHT * 0.66:
        colour = AMBER
    return colour


def pixel(x, y):
    """Четыре подвыборки на точку: без этого края стакана «лесенкой»."""
    parts = [sample(x + ox, y + oy) for ox, oy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))]
    return tuple(round(sum(part[channel] for part in parts) / 4) for channel in range(3))


def main() -> None:
    rows = bytearray()
    for y in range(HEIGHT):
        rows.append(0)  # фильтр строки: 0 — без фильтра
        for x in range(WIDTH):
            rows.extend(pixel(x, y))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )
    OUT.write_bytes(png)
    print(f"{OUT} — {len(png)} байт")


if __name__ == "__main__":
    main()
