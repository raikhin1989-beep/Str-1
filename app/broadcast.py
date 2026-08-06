"""Рассылка итогов в телеграм.

Отправка отмечается в таблице `delivery` и только при успехе. Поэтому кнопку
«разослать» можно нажать второй раз: тем, кому дошло, ничего не придёт, а тем,
у кого не получилось, и тем, кто привязал телеграм позже, — придёт.
"""

import html
import logging

from app import models, scoring, telegram

log = logging.getLogger("str1.broadcast")

KIND = "results"
TOP_SIZE = 3


def send_results(tasting_id: int, results_url: str) -> dict:
    """Разослать итоги. Возвращает отчёт: кому ушло, кого пропустили, где сбой."""
    tasting = models.get_tasting(tasting_id)
    if tasting is None:
        raise ValueError("дегустация не найдена")
    if tasting["status"] not in models.RESULT_STATUSES:
        raise ValueError("итоги ещё не подведены")

    board = models.leaderboard(tasting_id)
    if not board:
        raise ValueError("итоги не посчитаны — нажмите «Пересчитать»")

    scores = models.score_tasting(tasting_id)
    whiskies = {row["id"]: row["name"] for row in models.round_choices(tasting_id)}
    top = _top_lines(board)
    already = models.delivered(tasting_id, KIND)
    total_points = scoring.max_points(len(models.sample_numbers(tasting_id)))

    report = {"sent": [], "skipped": [], "failed": [], "unlinked": []}
    for row in board:
        if row["id"] in already:
            report["skipped"].append(row["name"])
            continue
        if not row["tg_chat_id"]:
            report["unlinked"].append(row["name"])
            continue
        text = compose(row, scores.get(row["id"]), whiskies, top, total_points,
                       tasting["title"], results_url, len(board),
                       models.category_title(tasting))
        if telegram.send_message(row["tg_chat_id"], text):
            models.mark_delivered(row["id"], KIND)
            report["sent"].append(row["name"])
        else:
            # Не падаем на первом же сбое: остальным сообщения нужны не меньше,
            # а этот участник попадёт в рассылку при повторном нажатии.
            log.warning("итоги не ушли участнику %s", row["id"])
            report["failed"].append(row["name"])
    return report


def pending(tasting_id: int, results_url: str) -> list[dict]:
    """Что осталось отправить: кому, куда и какой текст.

    Ничего не отправляет и ничего не отмечает — только готовит. Нужно для
    рассылки чужими руками: с этого сервера исходящие к api.telegram.org
    не проходят, поэтому сообщения отвозит раннер GitHub, у которого доступ
    есть (см. docs/RUNBOOK.md и job `broadcast` в деплое).
    """
    tasting = models.get_tasting(tasting_id)
    if tasting is None or tasting["status"] not in models.RESULT_STATUSES:
        return []
    board = models.leaderboard(tasting_id)
    if not board:
        return []

    scores = models.score_tasting(tasting_id)
    whiskies = {row["id"]: row["name"] for row in models.round_choices(tasting_id)}
    top = _top_lines(board)
    already = models.delivered(tasting_id, KIND)
    total_points = scoring.max_points(len(models.sample_numbers(tasting_id)))

    return [
        {
            "participant_id": row["id"],
            "chat_id": row["tg_chat_id"],
            "text": compose(row, scores.get(row["id"]), whiskies, top, total_points,
                            tasting["title"], results_url, len(board),
                            models.category_title(tasting)),
        }
        for row in board
        if row["tg_chat_id"] and row["id"] not in already
    ]


def latest_scored_tasting() -> int | None:
    """Последняя дегустация, у которой есть итоги. Ей и нужна рассылка."""
    for tasting in models.list_tastings():
        if tasting["status"] in models.RESULT_STATUSES:
            return int(tasting["id"])
    return None


def compose(row, score, whiskies, top, max_points, title, results_url, people,
            category_title: str = "класс") -> str:
    """Личное сообщение. HTML — потому что send_message шлёт с parse_mode=HTML.

    category_title — «класс» или «регион», смотря как заведена дегустация.
    Строку «за класс» на дегустации по регионам гость читает как ошибку
    в подсчёте, и на живом вечере именно так её и прочитали.
    """
    name = html.escape(row["name"])
    lines = [
        f"<b>{html.escape(title)}</b> — итоги.",
        "",
        f"{name}, ваше место: <b>{row['place']}</b> из {people}. "
        f"Очков: <b>{row['total']}</b> из {max_points}.",
        f"Нос {row['points_nose']}, вкус {row['points_palate']}, "
        f"за {category_title} {row['points_partial']}, бонусы {row['points_bonus']}.",
    ]

    if score is not None:
        hits = [s for s in score.samples if s.nose_id == s.truth_id or s.palate_id == s.truth_id]
        if hits:
            lines += ["", "Угадали:"]
            for sample in hits:
                how = []
                if sample.nose_id == sample.truth_id:
                    how.append("по запаху")
                if sample.palate_id == sample.truth_id:
                    how.append("по вкусу")
                lines.append(
                    f"№{sample.sample_no} {html.escape(whiskies.get(sample.truth_id, '—'))}"
                    f" — {' и '.join(how)}"
                )
        else:
            lines += ["", "В этот раз мимо — бывает."]

    lines += ["", "Топ-" + str(TOP_SIZE) + ":"] + top
    lines += ["", f'Полные итоги: {html.escape(results_url)}']
    return "\n".join(lines)


def summary_text(tasting, board, results_url: str) -> str:
    """Готовый текст итогов, чтобы отправить его руками.

    Нужен, когда сервер не может достучаться до api.telegram.org: с этого
    хостинга исходящие к телеграму не проходят, и кнопка рассылки бессильна,
    а вечер заканчивать всё равно надо. Текст без разметки — его копируют
    в чат как есть.
    """
    lines = [f"{tasting['title']} — итоги.", ""]
    for row in board:
        lines.append(f"{row['place']}. {row['name']} — {row['total']}")
    lines += ["", f"Подробности и разбор по образцам: {results_url}"]
    return "\n".join(lines)


def _top_lines(board) -> list[str]:
    return [
        f"{row['place']}. {html.escape(row['name'])} — {row['total']}"
        for row in board[:TOP_SIZE]
    ]
