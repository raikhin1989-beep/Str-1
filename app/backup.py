"""Резервные копии базы.

Копия снимается через `VACUUM INTO`, а не копированием файла: база работает
в режиме WAL, и просто скопированный `app.db` может оказаться без последних
записей, которые ещё лежат в `-wal`. `VACUUM INTO` даёт согласованный снимок
на живой базе, без остановки службы.

Ежедневную копию делает systemd-таймер (см. `.github/workflows/deploy.yml`),
он же зовёт `python -m app.backup`. Кнопка в админке снимает копию прямо
сейчас и отдаёт её файлом.
"""

import gzip
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.config import db_path
from app.db import connect

BACKUP_DIR = Path("/var/backups/str-1")
KEEP = 14


def snapshot(target: Path) -> Path:
    """Снять согласованную копию базы в указанный файл."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    # Соединение через connect(), чтобы схема точно была накатана: иначе
    # первый же бэкап на чистой машине снял бы копию пустого файла.
    conn = connect()
    try:
        # Путь подставляется в SQL строкой: VACUUM INTO не принимает параметр.
        # Имя файла собираем мы сами, оно не приходит извне.
        conn.execute(f"VACUUM INTO '{str(target)}'")
    finally:
        conn.close()
    return target


def daily(directory: Path = BACKUP_DIR, keep: int = KEEP) -> Path:
    """Ежедневная копия: снять, сжать, удалить лишние."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    raw = directory / f"app-{stamp}.db"
    snapshot(raw)

    archive = raw.with_suffix(".db.gz")
    with raw.open("rb") as source, gzip.open(archive, "wb") as target:
        shutil.copyfileobj(source, target)
    raw.unlink()

    prune(directory, keep)
    return archive


def prune(directory: Path, keep: int = KEEP) -> list[Path]:
    """Оставить последние `keep` копий, остальные удалить."""
    copies = sorted(directory.glob("app-*.db.gz"))
    doomed = copies[:-keep] if keep > 0 else copies
    for path in doomed:
        path.unlink()
    return doomed


def main() -> int:
    try:
        archive = daily()
    except Exception as err:  # pragma: no cover — путь таймера, не приложения
        print(f"бэкап не удался: {type(err).__name__}: {err}", file=sys.stderr)
        return 1
    print(f"{archive} — {archive.stat().st_size} байт, из {db_path()}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
