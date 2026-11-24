"""The parts of UserService that belong to the algorithm: reactions (D2)
and deleting algorithm data when consent is withdrawn (D3)."""

import pytest

from Backend.Logic.domain.story_reaction import Reaction
from Backend.Logic.exceptions import ConsentRequiredError, NotFoundError
from tests.backend.unit.algorithm.builders import (
    make_event,
    make_reaction,
    make_story,
    make_user,
    new_id,
)


def add_user(repo, users, *, consent=True):
    user = users.add(make_user(consent=consent))
    repo.add_user(user)
    return user


# ---- reactions ----------------------------------------------------------------------

def test_latest_reaction_wins(repo, users, user_service):
    user = add_user(repo, users)
    story = repo.add_story(make_story(), [])

    user_service.set_reaction(user.id, story.id, Reaction.like)
    user_service.set_reaction(user.id, story.id, Reaction.dislike)

    assert len(repo.reactions) == 1
    assert repo.reactions[(user.id, story.id)].reaction == Reaction.dislike


def test_unlike_removes_the_reaction(repo, users, user_service):
    user = add_user(repo, users)
    story = repo.add_story(make_story(), [])
    user_service.set_reaction(user.id, story.id, Reaction.like)

    user_service.remove_reaction(user.id, story.id)

    assert repo.reactions == {}


def test_reacting_without_consent_is_refused(repo, users, user_service):
    user = add_user(repo, users, consent=False)
    story = repo.add_story(make_story(), [])

    with pytest.raises(ConsentRequiredError):
        user_service.set_reaction(user.id, story.id, Reaction.like)

    assert repo.reactions == {}


def test_removing_a_reaction_needs_no_consent(repo, users, user_service):
    user = add_user(repo, users, consent=False)
    user_service.remove_reaction(user.id, new_id())  # must not raise


def test_reacting_to_an_unknown_story_is_not_found(repo, users, user_service):
    user = add_user(repo, users)

    with pytest.raises(NotFoundError):
        user_service.set_reaction(user.id, new_id(), Reaction.like)


# ---- consent withdrawn -------------------------------------------------------------

def test_withdrawing_consent_deletes_algorithm_data(repo, users, user_service):
    user = add_user(repo, users)
    story = repo.add_story(make_story(), [])
    user_service.set_reaction(user.id, story.id, Reaction.like)
    repo.scores[user.id] = {new_id(): 3.0}

    user_service.set_consent(user.id, False)

    assert repo.data_deleted_for == [user.id]
    assert repo.reactions == {}
    assert user.id not in repo.scores


@pytest.mark.parametrize("start, new", [(False, False), (True, True), (False, True)])
def test_other_consent_changes_delete_nothing(repo, users, user_service, start, new):
    user = add_user(repo, users, consent=start)

    user_service.set_consent(user.id, new)

    assert repo.data_deleted_for == []


# ---- listing reactions (so the app can show them again) -----------------------------
# The app stores likes and dislikes as engagement events, so the list is worked
# out from those (Algorithm/reactions.py), not from story_reactions.

def test_list_reactions_returns_the_users_current_reactions(repo, users, user_service):
    user = add_user(repo, users)
    liked = repo.add_story(make_story(), [])
    disliked = repo.add_story(make_story(), [])
    repo.events += [
        make_event(user.id, liked.id, "like"),
        make_event(user.id, disliked.id, "dislike"),
    ]

    reactions = {r.story_id: r.reaction for r in user_service.list_reactions(user.id)}

    assert reactions == {liked.id: Reaction.like, disliked.id: Reaction.dislike}


def test_list_reactions_shows_the_latest_tap(repo, users, user_service):
    user = add_user(repo, users)
    story = repo.add_story(make_story(), [])
    repo.events += [
        make_event(user.id, story.id, "like", happened_days_ago=2),
        make_event(user.id, story.id, "dislike", happened_days_ago=1),
    ]

    assert [r.reaction for r in user_service.list_reactions(user.id)] == [Reaction.dislike]


def test_list_reactions_leaves_out_an_undone_reaction(repo, users, user_service):
    user = add_user(repo, users)
    story = repo.add_story(make_story(), [])
    repo.events += [
        make_event(user.id, story.id, "like", happened_days_ago=1),
        make_event(user.id, story.id, "reaction_removed"),
    ]

    assert user_service.list_reactions(user.id) == []


def test_list_reactions_includes_old_ones(repo, users, user_service):
    # The algorithm only counts the last 30 days, but a like from long ago is still a like.
    user = add_user(repo, users)
    story = repo.add_story(make_story(), [])
    repo.events.append(make_event(user.id, story.id, "like", happened_days_ago=2000))

    assert [r.story_id for r in user_service.list_reactions(user.id)] == [story.id]


def test_list_reactions_ignores_the_story_reactions_table(repo, users, user_service):
    user = add_user(repo, users)
    story = repo.add_story(make_story(), [])
    repo.reactions[(user.id, story.id)] = make_reaction(user.id, story.id, Reaction.like)

    assert user_service.list_reactions(user.id) == []


def test_list_reactions_shows_only_this_users(repo, users, user_service):
    user, other = add_user(repo, users), add_user(repo, users)
    story = repo.add_story(make_story(), [])
    repo.events.append(make_event(other.id, story.id, "like"))

    assert user_service.list_reactions(user.id) == []


def test_list_reactions_for_an_unknown_user_is_not_found(user_service):
    with pytest.raises(NotFoundError):
        user_service.list_reactions(new_id())
