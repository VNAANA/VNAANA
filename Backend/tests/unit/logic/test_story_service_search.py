"""The search rules in StoryService: when q counts as a search and which
words get passed on to the repository."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from Backend.Logic.domain.story import StoryStatus
from Backend.Logic.exceptions import InvalidSearchError
from Backend.Logic.story_service import StoryService


@pytest.fixture
def stories():
    stories = Mock()
    stories.list.return_value = []
    return stories


@pytest.fixture
def service(stories):
    # articles and tags aren't touched by list_stories.
    return StoryService(stories=stories, articles=None, tags=None)


def search_terms_sent(stories):
    return stories.list.call_args.kwargs["search_terms"]


def test_no_q_means_no_search(service, stories):
    service.list_stories()

    assert search_terms_sent(stories) is None


@pytest.mark.parametrize("q", ["", "   ", "\t"])
def test_empty_q_means_no_search_instead_of_an_error(service, stories, q):
    service.list_stories(q=q)

    assert search_terms_sent(stories) is None


@pytest.mark.parametrize("q", ["a", " a ", "  é  "])
def test_q_shorter_than_two_characters_is_rejected(service, stories, q):
    with pytest.raises(InvalidSearchError):
        service.list_stories(q=q)

    stories.list.assert_not_called()


@pytest.mark.parametrize("q", ["EU", "AI", "VS"])
def test_two_letter_news_searches_are_allowed(service, stories, q):
    service.list_stories(q=q)

    assert search_terms_sent(stories) == [q]


def test_q_is_split_into_words(service, stories):
    service.list_stories(q="  flood   rotterdam\t port ")

    assert search_terms_sent(stories) == ["flood", "rotterdam", "port"]


def test_a_short_word_inside_a_longer_search_is_kept(service, stories):
    # Every word must match, so "a" can only narrow the results, never widen them.
    service.list_stories(q="flood a")

    assert search_terms_sent(stories) == ["flood", "a"]


def test_repeated_words_are_sent_once(service, stories):
    service.list_stories(q="flood rotterdam flood")

    assert search_terms_sent(stories) == ["flood", "rotterdam"]


def test_wildcard_characters_are_passed_on_as_typed(service, stories):
    # Escaping % and _ is SQL knowledge, so that happens in the DAL, not here.
    service.list_stories(q="100% zeker_niet")

    assert search_terms_sent(stories) == ["100%", "zeker_niet"]


def test_search_is_combined_with_the_other_filters(service, stories):
    tag_id = uuid4()

    service.list_stories(
        status=StoryStatus.published,
        tag_id=tag_id,
        q="flood",
        limit=5,
        offset=10,
    )

    stories.list.assert_called_once_with(
        status=StoryStatus.published,
        tag_id=tag_id,
        search_terms=["flood"],
        limit=5,
        offset=10,
    )
