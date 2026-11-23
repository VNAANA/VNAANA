from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from Backend.Logic.story_grouping import choose_story, representative, vectors_for
from Backend.Logic.story_grouping import clean_lead, exclusion_reason, event_conflict
from Backend.Logic.story_grouping import terms


def test_assessment_distinguishes_rejections():
    from Backend.Logic.story_grouping import MIN_SCORE, assess_story
    incoming, candidate = article(1, "Incoming"), article(2, "Candidate")
    vectors = {1: {"a": 1}, 2: {"a": MIN_SCORE / 2}}
    groups = {2: (candidate, [candidate])}
    assert assess_story(incoming, {}, vectors)["reason"] == "no candidate on the same publication day"
    assert assess_story(incoming, groups, vectors)["reason"] == "below threshold"
    vectors[2] = {"a": 1}
    groups[3] = (candidate, [candidate])
    assert assess_story(incoming, groups, vectors)["reason"] == "too close to the runner-up"


def test_decision_reports_representative_and_ambiguity_without_rounding():
    from Backend.Logic.story_grouping import assess_story
    first, second, incoming = [article(i, str(i)) for i in (1, 2, 3)]
    vectors = {1: {"x": .50}, 2: {"x": .48}, 3: {"x": 1}}
    result = assess_story(incoming, {1: (first, [first]), 2: (second, [second])}, vectors)
    assert result["reason"] == "too close to the runner-up"
    assert result["best_candidate"]["matched_article_id"] == "1"
    assert result["best_candidate"]["score"] == .50
    assert result["runner_up"]["score"] == .48
    assert abs(result["score_gap"] - .02) < 1e-12
    assert result["best_candidate"]["representatives"] == [{"article_id": "1", "score": .50}]


def article(key, title, *, days=0, content=None):
    return SimpleNamespace(id=key, title=title, description=None, content=content,
                           published_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=days))


def test_repeated_headline_outside_window_and_ambiguous_matches():
    first = article(1, "Storm legt treinverkeer Utrecht stil")
    incoming = article(2, first.title, days=4)
    vectors = vectors_for([first, incoming])
    group = (first, [first])
    assert choose_story(incoming, {1: group}, vectors) is None
    incoming.published_at = first.published_at
    assert choose_story(incoming, {1: group}, vectors) == 1
    assert choose_story(incoming, {1: group, 2: group}, vectors) is None


def test_representative_is_central_even_with_syndicated_copies():
    titles = ["brand haven", "brand haven rook schip", "rook schip"]
    members = [article(i, title) for i, title in enumerate(titles + [titles[0]] * 4)]
    assert representative(members, vectors_for(members)).id == 1


def test_clean_lead_skips_navigation_and_repeated_title():
    story = article(1, "Brand in Rotterdam", content=(
        "Sluiten\nAl abonnee?\nInloggen\nBrand in Rotterdam\n"
        "Feitelijke berichtgeving, waargenomen en geverifieerd door de verslaggever\n"
        "De brandweer heeft een grote brand in de Rotterdamse haven onder controle gekregen."
    ))
    assert clean_lead(story).startswith("De brandweer")
    assert exclusion_reason(story) is None
    story.content = "Sluiten\nAl abonnee?\nInloggen"
    assert exclusion_reason(story) == "navigation without usable article text"


def test_non_news_pages_are_excluded_but_general_reporting_is_kept():
    assert exclusion_reason(article(1, "Sudoku")) == "puzzle page"
    assert exclusion_reason(article(1, "Samsung Black Friday aanbieding met gratis tablet")) == "shopping promotion"
    assert exclusion_reason(article(1, "Black Friday zorgt voor drukte in winkelstraten")) is None


def test_templates_distinguish_towns_and_dates_but_allow_updated_death_toll():
    assert event_conflict(article(1, "Openstelling burgemeestersvacature Beverwijk"),
                          article(2, "Openstelling burgemeestersvacature Leeuwarden"))
    assert event_conflict(article(1, "Persconferentie na ministerraad 6 november 2026"),
                          article(2, "Persconferentie na ministerraad 30 oktober 2026"))
    assert not event_conflict(article(1, "Boot gezonken Senegal: 34 doden"),
                              article(2, "Boot gezonken Senegal: 39 doden"))


def test_conflict_blocks_link_even_when_vectors_are_identical():
    first = article(1, "Openstelling burgemeestersvacature Beverwijk")
    second = article(2, "Openstelling burgemeestersvacature Leeuwarden")
    assert choose_story(second, {1: (first, [first])}, {1: {"a": 1}, 2: {"a": 1}}) is None


def test_member_can_match_when_primary_does_not():
    primary = article(1, "Primary")
    member = article(2, "Other coverage")
    incoming = article(3, "Incoming coverage")
    vectors = {1: {"a": 1}, 2: {"b": 1}, 3: {"b": 1}}
    groups = {1: (primary, [primary, member])}
    assert choose_story(incoming, groups, vectors, representative_limit=1) is None
    assert choose_story(incoming, groups, vectors) == 1


def test_more_representatives_still_require_clear_winning_story():
    primary, member, incoming = [article(i, "Coverage") for i in range(3)]
    vectors = {0: {"a": 1}, 1: {"b": 1}, 2: {"b": 1}}
    groups = {1: (primary, [primary, member]), 2: (member, [member])}
    assert choose_story(incoming, groups, vectors) is None


def test_terms_include_title_description_and_content():
    item = article(1, "HeadlineOnly", content=(
        "De brandweer heeft een grote brand in de Rotterdamse haven onder controle gekregen."
    ))
    item.description = "DescriptionOnly"
    content_terms = terms(item)
    assert "rotterdamse" in content_terms
    assert content_terms["headlineonly"] == 2
    assert "descriptiononly" in content_terms
    assert terms(item)["headlineonly"] == 2


def test_old_primary_cannot_bypass_window_through_recent_unrelated_member():
    old = article(1, "Old", days=0)
    recent = article(2, "Recent", days=4)
    incoming = article(3, "Incoming", days=4)
    vectors = {1: {"a": 1}, 2: {"b": 1}, 3: {"a": 1}}
    assert choose_story(incoming, {1: (old, [old, recent])}, vectors) is None


def test_identical_articles_on_different_days_stay_separate():
    first, second = article(1, "First"), article(2, "Second")
    incoming = article(3, "Incoming", days=1)
    vectors = {1: {"a": 1}, 2: {"a": 0.8, "b": 0.6}, 3: {"a": 1}}
    assert choose_story(incoming, {1: (first, [first, second])}, vectors) is None


def test_amsterdam_midnight_splits_articles_two_minutes_apart():
    first, incoming = article(1, "Storm"), article(2, "Storm")
    first.published_at += timedelta(hours=22, minutes=59)
    incoming.published_at += timedelta(hours=23, minutes=1)
    vectors = {1: {"a": 1}, 2: {"a": 1}}
    assert choose_story(incoming, {1: (first, [first])}, vectors) is None


def test_different_utc_dates_can_share_amsterdam_day():
    first, incoming = article(1, "Storm"), article(2, "Storm", days=1)
    first.published_at += timedelta(hours=23)
    vectors = {1: {"a": 1}, 2: {"a": 1}}
    assert choose_story(incoming, {1: (first, [first])}, vectors) == 1


def test_publication_day_falls_back_to_first_seen():
    from Backend.Logic.story_grouping import article_day
    item = article(1, "Storm")
    item.first_seen_at, item.published_at = item.published_at, None
    assert article_day(item).isoformat() == "2026-01-01"


def test_summer_timezone_uses_daylight_saving():
    from Backend.Logic.story_grouping import article_day
    item = article(1, "Storm")
    item.published_at = datetime(2026, 7, 1, 22, 30, tzinfo=timezone.utc)
    assert article_day(item).isoformat() == "2026-07-02"
