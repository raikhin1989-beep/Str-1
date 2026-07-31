"""Подсчёт очков — чистые функции.

Здесь нет ни базы, ни запросов: на вход приходят словари, на выход — числа.
Так правила можно проверить тестами до последнего крайнего случая, а сам
подсчёт остаётся воспроизводимым: одни и те же ответы всегда дают один
и тот же результат.

Правила и их обоснование — в docs/SCORING.md. Менять их надо в двух местах
одновременно: там и здесь.
"""

from dataclasses import dataclass, field

POINTS_NOSE = 3
POINTS_PALATE = 2
POINTS_CATEGORY = 1
POINTS_CONSISTENCY = 1
POINTS_CLEAN_ROUND = 3

# При одном-двух образцах «раунд без ошибок» — это не мастерство, а совпадение,
# и бонус превращается в подарок. С трёх образцов он снова что-то значит.
MIN_SAMPLES_FOR_CLEAN_ROUND = 3

ROUND_POINTS = {"nose": POINTS_NOSE, "palate": POINTS_PALATE}


@dataclass
class SampleResult:
    """Что вышло по одному образцу — для личного разбора после итогов."""

    sample_no: int
    truth_id: int
    nose_id: int | None = None
    palate_id: int | None = None
    nose_points: int = 0
    palate_points: int = 0
    consistent: bool = False

    @property
    def points(self) -> int:
        return self.nose_points + self.palate_points + (POINTS_CONSISTENCY if self.consistent else 0)


@dataclass
class Score:
    points_nose: int = 0
    points_palate: int = 0
    points_partial: int = 0
    points_bonus: int = 0
    clean_nose: bool = False
    clean_palate: bool = False
    answered: bool = False
    samples: list[SampleResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.points_nose + self.points_palate + self.points_partial + self.points_bonus


def max_points(sample_count: int) -> int:
    """Потолок при таком числе образцов — его показываем рядом с результатом."""
    total = sample_count * (POINTS_NOSE + POINTS_PALATE + POINTS_CONSISTENCY)
    if sample_count >= MIN_SAMPLES_FOR_CLEAN_ROUND:
        total += 2 * POINTS_CLEAN_ROUND
    return total


def score_participant(
    truth: dict[int, int],
    answers: dict[str, dict[int, int]],
    categories: dict[int, str | None] | None = None,
) -> Score:
    """Очки одного участника.

    truth      — что налито: номер образца → id виски;
    answers    — {"nose": {номер: id}, "palate": {номер: id}}, любой может быть пуст;
    categories — id виски → категория (класс или регион, выбирает админ).
    """
    categories = categories or {}
    score = Score()
    per_sample: dict[int, SampleResult] = {
        sample_no: SampleResult(sample_no=sample_no, truth_id=truth_id)
        for sample_no, truth_id in sorted(truth.items())
    }

    for round_name in ("nose", "palate"):
        given = answers.get(round_name) or {}
        if given:
            score.answered = True
        hits = 0
        for sample_no, truth_id in truth.items():
            chosen = given.get(sample_no)
            if chosen is None:
                continue
            result = per_sample[sample_no]
            setattr(result, f"{round_name}_id", chosen)
            if chosen == truth_id:
                hits += 1
                points = ROUND_POINTS[round_name]
                setattr(result, f"{round_name}_points", points)
                if round_name == "nose":
                    score.points_nose += points
                else:
                    score.points_palate += points
            elif _same_category(categories, chosen, truth_id):
                # Частичный балл вместо полного, а не вдобавок к нему:
                # за образец начисляется что-то одно.
                setattr(result, f"{round_name}_points", POINTS_CATEGORY)
                score.points_partial += POINTS_CATEGORY

        # Чистый раунд — это все образцы, а не все отвеченные: иначе выгоднее
        # было бы ответить на один и промолчать про остальные.
        if truth and hits == len(truth) and len(truth) >= MIN_SAMPLES_FOR_CLEAN_ROUND:
            score.points_bonus += POINTS_CLEAN_ROUND
            if round_name == "nose":
                score.clean_nose = True
            else:
                score.clean_palate = True

    for result in per_sample.values():
        if result.nose_id == result.truth_id and result.palate_id == result.truth_id:
            result.consistent = True
            score.points_bonus += POINTS_CONSISTENCY

    score.samples = [per_sample[no] for no in sorted(per_sample)]
    return score


def _same_category(categories: dict[int, str | None], chosen: int, truth_id: int) -> bool:
    """Один ли класс (или регион) у названного и у верного.

    Пустая категория не совпадает ни с чем, даже с другой пустой: иначе два
    виски без проставленной категории приносили бы балл ни за что.
    """
    mine = (categories.get(chosen) or "").strip().casefold()
    theirs = (categories.get(truth_id) or "").strip().casefold()
    return bool(mine) and mine == theirs


def rank(scores: dict[int, Score], submitted_at: dict[int, str | None]) -> list[tuple[int, int]]:
    """Расставить по местам: [(participant_id, место)].

    Тай-брейк по docs/SCORING.md: сумма, затем очки за нос, затем кто раньше
    отправил второй раунд. При полном равенстве место делится — два вторых
    места, третьего нет.
    """
    def key(participant_id: int):
        score = scores[participant_id]
        when = submitted_at.get(participant_id) or "9999"
        return (-score.total, -score.points_nose, when)

    ordered = sorted(scores, key=key)
    places: list[tuple[int, int]] = []
    place = 0
    previous = None
    for index, participant_id in enumerate(ordered, start=1):
        current = key(participant_id)
        # Делим место только при полном равенстве, включая время отправки:
        # иначе тай-брейк не был бы тай-брейком.
        if current != previous:
            place = index
            previous = current
        places.append((participant_id, place))
    return places
