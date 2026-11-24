"""The For You algorithm through the whole backend, on the real migrated Postgres.

Everything below the browser is real: the API routes, UserService,
AlgorithmService, the scoring/decay/ranking code, AlgorithmRepository,
the hourly job (Backend/run_algorithm.py) and the database built by the
migrations. Only the Supabase login is replaced by a fixed test user, so this
runs without signing in.

The flow follows a real user: sign in, give consent, pick a topic during
onboarding, react to stories, let the hourly job run, read the feed, and
finally withdraw consent.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from Backend.config import get_settings
from Backend.Dal.models import Story, StoryStatus, StoryTag, Tag
from Backend.Dal.repositories.algorithm_repository import AlgorithmRepository

SUBJECT = uuid.uuid4()  # the Supabase user id the fake login hands out


@pytest.fixture
def client(db, new_session, monkeypatch):
    # The app reads its settings when it's imported; keep a developer's own
    # .env (and the real Supabase) out of it.
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    get_settings.cache_clear()

    from Backend.database import get_db
    from Backend.main import app
    from Backend.Presentation.auth import get_authenticated_subject, get_optional_subject

    def one_session_per_request():
        # Like Backend.database.get_db, but inside the test's transaction.
        session = new_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = one_session_per_request
    app.dependency_overrides[get_authenticated_subject] = lambda: SUBJECT
    app.dependency_overrides[get_optional_subject] = lambda: SUBJECT
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        get_settings.cache_clear()


@pytest.fixture
def stories(db) -> dict[str, uuid.UUID]:
    """One published story per topic, tagged with the tags the migrations seed.

    Stories come from the news pipeline, not from users, so they're added
    straight to the database.
    """
    # Newest first is the OPPOSITE of the order the algorithm should produce,
    # so a feed that ignores the scores (and only sorts by date) fails the test.
    now = datetime.now(timezone.utc)
    ids = {}
    for minutes_ago, topic in enumerate(("Politics", "Climate", "Sports", "Technology")):
        tag = db.scalar(select(Tag).where(Tag.name == topic))
        story = Story(
            title=f"{topic} story",
            status=StoryStatus.published,
            last_updated_at=now - timedelta(minutes=minutes_ago),
        )
        db.add(story)
        db.flush()
        db.add(StoryTag(story_id=story.id, tag_id=tag.id))
        ids[topic] = story.id
    db.commit()
    return ids


def run_hourly_job(new_session, monkeypatch) -> None:
    """The real Backend/run_algorithm.py, with its session inside the test transaction."""
    import Backend.run_algorithm as job

    monkeypatch.setattr(job, "SessionLocal", new_session)
    job.main()


def feed(client) -> dict:
    response = client.get("/stories/for-you")
    assert response.status_code == 200, response.text
    return response.json()


def titles(feed_body: dict) -> list[str]:
    return [ranked["story"]["title"] for ranked in feed_body["stories"]]


def test_the_for_you_feed_through_the_whole_backend(client, stories, new_session, monkeypatch):
    # Signing in creates the user; consent is off by default.
    user = client.post("/users/me/bootstrap")
    assert user.status_code in (200, 201), user.text
    user_id = user.json()["id"]
    assert feed(client)["status"] == "no_consent"

    # Consent on, but nothing known about the user yet.
    client.put(f"/users/{user_id}/consent", json={"analytics_consent": True}).raise_for_status()
    assert feed(client)["status"] == "locked"

    # Onboarding: picking a topic unlocks For You right away.
    tags = {tag["name"]: tag["id"] for tag in client.get("/tags").json()}
    client.put(f"/users/{user_id}/tags", json={"tag_ids": [tags["Technology"]]}).raise_for_status()
    assert feed(client)["status"] == "available"

    # Reacting to stories: like Sports (+2), dislike Politics (-5), read Climate to the end (+1).
    # Like the app, every tap is an engagement event (Frontend/src/utils/engagement.ts).
    session_id = str(uuid.uuid4())
    for topic, event_type in (("Sports", "like"), ("Politics", "dislike"), ("Climate", "read_complete")):
        client.post(
            f"/users/{user_id}/events",
            json={"session_id": session_id, "story_id": str(stories[topic]), "event_type": event_type},
        ).raise_for_status()
    reactions = {r["story_id"]: r["reaction"] for r in client.get(f"/users/{user_id}/reactions").json()}
    assert reactions == {str(stories["Sports"]): "like", str(stories["Politics"]): "dislike"}

    expected_order = ["Technology story", "Sports story", "Climate story", "Politics story"]

    # Before the job has run nothing is stored, but the feed is already personal:
    # a new user is scored on the spot.
    reader = AlgorithmRepository(new_session())
    assert reader.get_tag_scores(uuid.UUID(user_id)) == {}
    assert titles(feed(client)) == expected_order

    run_hourly_job(new_session, monkeypatch)

    # The job stored a score per tag: declared Technology (+5), Sports +2, Climate +1, Politics -5.
    stored = reader.get_tag_scores(uuid.UUID(user_id))
    by_name = {name: stored.get(uuid.UUID(tag_id)) for name, tag_id in tags.items() if uuid.UUID(tag_id) in stored}
    assert by_name == pytest.approx({"Technology": 5, "Sports": 2, "Climate": 1, "Politics": -5}, abs=0.01)

    # And the feed, now reading the stored scores, puts the stories in that order.
    body = feed(client)
    assert body["status"] == "available"
    assert titles(body) == expected_order

    # The job runs every hour: a second run must give the same scores, not
    # stack anything on top (for example treating scored tags as declared).
    run_hourly_job(new_session, monkeypatch)
    assert reader.get_tag_scores(uuid.UUID(user_id)) == pytest.approx(stored, abs=0.01)
    assert titles(feed(client)) == expected_order

    # Withdrawing consent: no personal feed, reactions and scores gone straight away.
    client.put(f"/users/{user_id}/consent", json={"analytics_consent": False}).raise_for_status()
    assert feed(client)["status"] == "no_consent"
    assert reader.get_tag_scores(uuid.UUID(user_id)) == {}
    assert client.get(f"/users/{user_id}/reactions").json() == []


def test_a_new_user_without_consent_is_never_scored_by_the_job(client, stories, new_session, monkeypatch):
    user_id = client.post("/users/me/bootstrap").json()["id"]

    run_hourly_job(new_session, monkeypatch)

    assert AlgorithmRepository(new_session()).get_tag_scores(uuid.UUID(user_id)) == {}
    assert feed(client)["status"] == "no_consent"


class FakeTranslator:
    """Stands in for Google: prefixes every text with EN: and remembers the calls."""

    def __init__(self):
        self.calls = []
        self.fail = False

    def translate(self, texts, *, source, target):
        from Backend.Logic.exceptions import TranslationUnavailableError

        self.calls.append(list(texts))
        if self.fail:
            raise TranslationUnavailableError("Translation quota exceeded")
        return [f"EN:{text}" for text in texts]


def test_an_english_user_translates_a_post_and_the_feed_shows_it(client, stories, db):
    from Backend.Dal.models import Article, Provider, StoryArticle, StoryTranslation
    from Backend.main import app
    from Backend.Presentation.dependencies import get_translator

    # The Technology story leads with an article, whose description the card shows.
    provider = Provider(name="NOS", domain="nos.test", reliability_status="verified")
    db.add(provider)
    db.flush()
    article = Article(
        provider_id=provider.id,
        canonical_url="https://nos.test/tech",
        title="Artikel",
        description="Beschrijving",
    )
    db.add(article)
    db.flush()
    db.add(StoryArticle(story_id=stories["Technology"], article_id=article.id, is_primary=True))
    db.commit()

    translator = FakeTranslator()
    app.dependency_overrides[get_translator] = lambda: translator

    user_id = client.post("/users/me/bootstrap").json()["id"]
    client.patch(f"/users/{user_id}", json={"language": "en"}).raise_for_status()
    client.put(f"/users/{user_id}/consent", json={"analytics_consent": True}).raise_for_status()
    tags = {tag["name"]: tag["id"] for tag in client.get("/tags").json()}
    client.put(f"/users/{user_id}/tags", json={"tag_ids": [tags["Technology"]]}).raise_for_status()

    # Loading the feed never translates: everything is still Dutch.
    body = feed(client)
    assert titles(body)[0] == "Technology story"
    assert body["stories"][0]["story"]["translated_into"] is None
    assert translator.calls == []

    # The Translate button: the story's text and the lead article's
    # description go to Google in one call and come back translated.
    response = client.post(f"/stories/{stories['Technology']}/translation")
    assert response.status_code == 200, response.text
    card = response.json()
    assert card["title"] == "EN:Technology story"
    assert card["lead_article"]["description"] == "EN:Beschrijving"
    assert card["translated_into"] == "en"
    assert translator.calls == [["Technology story", "Beschrijving"]]

    # Saved in story_translations, description included.
    saved = db.get(StoryTranslation, (stories["Technology"], "en"))
    db.refresh(saved)
    assert (saved.title, saved.description) == ("EN:Technology story", "EN:Beschrijving")

    # From now on the feed shows the saved translation, even with Google down;
    # the stories nobody translated stay Dutch.
    translator.fail = True
    body = feed(client)
    assert titles(body)[0] == "EN:Technology story"
    assert body["stories"][0]["story"]["lead_article"]["description"] == "EN:Beschrijving"
    assert body["stories"][0]["story"]["translated_into"] == "en"
    assert "Sports story" in titles(body)
    # The general story list (Explore) shows it too.
    listed = {story["id"]: story for story in client.get("/stories").json()}
    assert listed[str(stories["Technology"])]["title"] == "EN:Technology story"
    assert len(translator.calls) == 1

    # Translate while Google is down: a 503 and nothing changes.
    sports = client.post(f"/stories/{stories['Sports']}/translation")
    assert sports.status_code == 503
    assert db.get(StoryTranslation, (stories["Sports"], "en")) is None

    # A story that changed after translating shows its new Dutch text again
    # instead of an outdated translation.
    db.get(Story, stories["Technology"]).title = "Nieuw verhaal"
    db.get(Story, stories["Technology"]).last_updated_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    db.commit()
    body = feed(client)
    assert body["status"] == "available"
    assert "Nieuw verhaal" in titles(body)
