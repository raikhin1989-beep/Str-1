"""Из чего участник выбирает ответ и как от этого зависят частичные баллы."""

import pytest

from app import models, scoring


@pytest.fixture
def evening():
    """Налито два односолодовых; в справочнике есть третий, того же класса."""
    tasting_id = models.create_tasting("Первая", None, "class")
    poured = [
        models.save_whisky({"name": name, "wclass": "односолодовый скотч"})
        for name in ("Aberlour Suthainn", "The Dalmore The Quartet")
    ]
    for whisky_id in poured:
        models.add_whisky_to_tasting(tasting_id, whisky_id)
    same_class = models.save_whisky({"name": "Ardbeg 10", "wclass": "односолодовый скотч"})
    other_class = models.save_whisky({"name": "Jim Beam", "wclass": "бурбон"})

    models.set_status(tasting_id, "registration")
    token = models.register_participant(tasting_id, "Саша")
    person = models.get_participant_by_token(token)["id"]
    models.set_status(tasting_id, "round_nose")
    return {
        "id": tasting_id, "token": token, "person": person, "poured": poured,
        "same_class": same_class, "other_class": other_class,
        "truth": models.tasting_truth(tasting_id),
    }


def test_by_default_the_whole_catalogue_is_offered(evening):
    names = [row["name"] for row in models.round_choices(evening["id"])]
    assert "Ardbeg 10" in names, "виски не со стола тоже вариант"
    assert "Jim Beam" in names


def test_naming_a_whisky_of_the_same_class_earns_the_partial_point(evening):
    """Ради этого выбор и расширен: раньше промахнуться в свой класс можно было
    только переставив два образца местами."""
    first = min(evening["truth"])
    models.save_round_draft(evening["person"], "nose", {first: evening["same_class"]})
    score = models.score_tasting(evening["id"])[evening["person"]]
    assert score.points_partial == 1
    assert score.points_nose == 0


def test_a_wrong_class_earns_nothing(evening):
    first = min(evening["truth"])
    models.save_round_draft(evening["person"], "nose", {first: evening["other_class"]})
    assert models.score_tasting(evening["id"])[evening["person"]].total == 0


def test_the_right_answer_still_earns_full_points(evening):
    models.save_round_draft(evening["person"], "nose", dict(evening["truth"]))
    score = models.score_tasting(evening["id"])[evening["person"]]
    assert score.points_nose == 2 * scoring.POINTS_NOSE


def test_one_name_still_cannot_go_to_two_samples(evening):
    numbers = sorted(evening["truth"])
    with pytest.raises(ValueError, match="двум образцам"):
        models.save_round_draft(
            evening["person"], "nose",
            {numbers[0]: evening["same_class"], numbers[1]: evening["same_class"]},
        )


def test_the_page_warns_that_the_list_is_wider_than_the_table(client, evening):
    page = client.get(f"/me/{evening['token']}").text
    assert "весь справочник" in page
    assert "за верный класс тоже дают балл" in page


def test_the_admin_can_narrow_it_back_before_the_rounds(admin):
    tasting_id = models.create_tasting("Полегче", None, "class")
    admin.post(
        f"/admin/tastings/{tasting_id}",
        data={"title": "Полегче", "held_on": "", "category_level": "class",
              "answer_scope": "tasting"},
        follow_redirects=True,
    )
    assert models.get_tasting(tasting_id)["answer_scope"] == "tasting"


def test_the_admin_page_says_how_many_options_there_are(admin, evening):
    page = admin.get(f"/admin/tastings/{evening['id']}").text
    assert "Участник выбирает ответ" in page
    assert "названий" in page
