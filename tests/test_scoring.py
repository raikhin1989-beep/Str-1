"""Правила подсчёта очков. Крайние случаи — из docs/SCORING.md."""

from app import scoring

# Пять образцов: что в них налито на самом деле.
TRUTH = {1: 10, 2: 20, 3: 30, 4: 40, 5: 50}

# Классы: 10 и 20 — односолодовые, 30 и 40 — купажи, 50 сам по себе.
CATEGORIES = {
    10: "односолодовый скотч",
    20: "односолодовый скотч",
    30: "купажированный скотч",
    40: "купажированный скотч",
    50: "теннесси",
}


def score(nose=None, palate=None, truth=None, categories=CATEGORIES):
    return scoring.score_participant(
        truth if truth is not None else TRUTH,
        {"nose": nose or {}, "palate": palate or {}},
        categories,
    )


def test_nothing_answered_is_zero_but_still_a_result():
    result = score()
    assert result.total == 0
    assert result.answered is False
    assert len(result.samples) == 5, "в таблице участник не исчезает"


def test_a_nose_hit_is_worth_three():
    assert score(nose={1: 10}).points_nose == 3


def test_a_palate_hit_is_worth_two():
    assert score(palate={1: 10}).points_palate == 2


def test_same_class_miss_is_worth_one():
    """Промахнулся, но назвал виски того же класса."""
    result = score(nose={1: 20})
    assert result.points_partial == 1
    assert result.points_nose == 0


def test_a_miss_across_classes_is_worth_nothing():
    assert score(nose={1: 30}).total == 0


def test_partial_and_full_do_not_stack():
    """За образец начисляется либо полный балл, либо частичный, либо ноль."""
    result = score(nose={1: 10})
    assert result.points_nose == 3 and result.points_partial == 0


def test_empty_category_matches_nothing():
    """Два виски без класса не должны приносить балл ни за что."""
    result = score(nose={1: 20}, categories={10: None, 20: ""})
    assert result.total == 0


def test_guessing_a_sample_in_both_rounds_adds_a_bonus():
    result = score(nose={1: 10}, palate={1: 10})
    assert result.points_bonus == 1
    assert result.total == 3 + 2 + 1


def test_two_different_answers_give_no_consistency_bonus():
    result = score(nose={1: 10}, palate={1: 20})
    assert result.points_bonus == 0


def test_a_clean_round_adds_three():
    result = score(nose=dict(TRUTH))
    assert result.clean_nose is True
    assert result.points_bonus == 3
    assert result.points_nose == 15


def test_a_perfect_game_hits_the_documented_maximum():
    result = score(nose=dict(TRUTH), palate=dict(TRUTH))
    assert result.total == scoring.max_points(5) == 36


def test_clean_round_needs_every_sample_not_just_the_answered_ones():
    """Иначе выгоднее ответить на один образец и промолчать про остальные."""
    result = score(nose={1: 10})
    assert result.clean_nose is False
    assert result.total == 3


def test_two_samples_give_no_clean_round_bonus():
    """При одном-двух образцах безошибочный раунд — совпадение, а не мастерство."""
    small = {1: 10, 2: 20}
    result = score(nose=dict(small), palate=dict(small), truth=small)
    assert result.points_bonus == 2, "только постоянство, без бонуса за чистый раунд"
    assert scoring.max_points(2) == 2 * 6


def test_the_example_from_the_docs_adds_up():
    """Пример из docs/SCORING.md: 2 по запаху, 4 по вкусу, один промах в класс."""
    result = score(
        nose={1: 10, 2: 20, 3: 40, 4: 50, 5: 30},
        palate={1: 10, 2: 20, 3: 30, 4: 40, 5: 10},
    )
    # нос: два попадания (6) + промах 3→40 того же класса (1)
    # вкус: четыре попадания (8)
    # постоянство: образцы 1 и 2 (2)
    assert result.points_nose == 6
    assert result.points_palate == 8
    assert result.points_partial == 1
    assert result.points_bonus == 2
    assert result.total == 17


def test_partial_answers_count_only_what_is_filled():
    result = score(nose={2: 20, 5: 50})
    assert result.points_nose == 6
    assert result.samples[0].nose_id is None


def test_sample_breakdown_says_what_happened():
    result = score(nose={1: 10, 2: 30}, palate={1: 10})
    first, second = result.samples[0], result.samples[1]
    assert first.nose_points == 3 and first.palate_points == 2 and first.consistent
    assert first.points == 6
    assert second.nose_points == 0, "30 — другой класс, чем 20"


# ── места и тай-брейк ──────────────────────────────────────────────────────


def test_places_go_by_total():
    scores = {1: score(nose={1: 10}), 2: score(nose=dict(TRUTH))}
    assert scoring.rank(scores, {}) == [(2, 1), (1, 2)]


def test_tie_is_broken_by_nose_points():
    """Одинаковая сумма — выше тот, кто взял её носом."""
    by_nose = score(nose={1: 10, 2: 20})            # 6
    by_palate = score(palate={1: 10, 2: 20, 3: 30}) # 6
    places = dict(scoring.rank({1: by_palate, 2: by_nose}, {}))
    assert places[2] == 1 and places[1] == 2


def test_tie_is_broken_by_who_finished_earlier():
    first = score(nose={1: 10})
    second = score(nose={1: 10})
    places = dict(scoring.rank({1: first, 2: second}, {1: "12:05", 2: "12:01"}))
    assert places[2] == 1 and places[1] == 2


def test_complete_equality_shares_the_place():
    scores = {1: score(nose={1: 10}), 2: score(nose={1: 10}), 3: score()}
    places = dict(scoring.rank(scores, {1: "12:00", 2: "12:00"}))
    assert places[1] == places[2] == 1
    assert places[3] == 3, "после двух первых идёт третье место, а не второе"
