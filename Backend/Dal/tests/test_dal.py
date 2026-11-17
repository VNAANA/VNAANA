"""Checking the table schemas before continue"""
import unittest
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, configure_mappers
from sqlalchemy.schema import CreateTable

from Backend.Dal.models import (
    Article, Base, EngagementEvent, Provider, ProviderSource, Story,
    StoryArticle, StoryStatus, StoryTag, Tag, User, UserTag,
    EventWeight, StoryReaction,
)
from Backend.Dal.repositories import ArticleRepository, UserRepository, EngagementEventRepository
from Backend.Logic.exceptions import NotFoundError
from Backend.Dal.repositories.story_grouping import group_articles
from sqlalchemy.exc import IntegrityError
from Backend.Presentation.schemas.users import UserCreate, UserRead, EngagementEventRead


@compiles(JSONB, "sqlite")
def compile_test_jsonb(type_, compiler, **kwargs):
    return "JSON"


class SchemaTests(unittest.TestCase):
    def test_revised_columns_and_indexes(self):
        self.assertTrue(any(
            type(constraint).__name__ == "UniqueConstraint"
            and list(constraint.columns.keys()) == ["auth_provider", "auth_subject"]
            for constraint in User.__table__.constraints
        ))
        for column in (User.__table__.c.auth_provider, User.__table__.c.auth_subject,
                       UserTag.__table__.c.is_declared, UserTag.__table__.c.score,
                       EngagementEvent.__table__.c.ingested_at):
            self.assertFalse(column.nullable)
            self.assertIsNone(column.server_default)
            self.assertIsNone(column.default)
        for column in (User.__table__.c.affinity_updated_at, UserTag.__table__.c.computed_at):
            self.assertTrue(column.nullable)
            self.assertTrue(column.type.timezone)
        self.assertTrue(EngagementEvent.__table__.c.ingested_at.type.timezone)
        self.assertEqual(str(UserTag.__table__.c.score.type.compile(dialect=postgresql.dialect())), "FLOAT")
        self.assertEqual(list(EventWeight.__table__.primary_key.columns.keys()), ["event_type"])
        self.assertEqual(str(EventWeight.__table__.c.weight.type), "NUMERIC(6, 2)")
        self.assertFalse(EventWeight.__table__.c.weight.nullable)
        fk = next(iter(EngagementEvent.__table__.c.event_type.foreign_keys))
        self.assertEqual(fk.target_fullname, "event_weights.event_type")
        self.assertEqual(fk.name, "fk_engagement_events_event_type")
        self.assertEqual(
            {tuple(index.columns.keys()) for index in EngagementEvent.__table__.indexes},
            {("user_id", "occurred_at"), ("story_id", "occurred_at"), ("session_id", "occurred_at")},
        )

    def test_postgresql_schema_contract(self):
        configure_mappers()
        self.assertEqual([s.value for s in StoryStatus], ["draft", "published", "archived"])
        self.assertEqual(Story.__table__.c.status.default.arg, StoryStatus.draft)
        self.assertEqual(Story.__table__.c.status.server_default.arg, "draft")
        self.assertEqual(Story.__table__.c.status.type.enums, ["draft", "published", "archived"])
        self.assertEqual(len(Base.metadata.tables), 12)
        self.assertNotIn("age_band", User.__table__.c)
        self.assertNotIn("region", User.__table__.c)
        self.assertEqual(sum(len(t.columns) for t in Base.metadata.tables.values()), 77)
        expected_server_defaults = {
            ("users", "onboarding_completed"),
            ("users", "analytics_consent"),
            ("providers", "created_at"),
            ("articles", "first_seen_at"),
            ("articles", "last_seen_at"),
            ("stories", "status"),
            ("stories", "last_updated_at"),
            ("story_articles", "is_primary"),
            ("story_articles", "added_at"),
            ("user_tags", "updated_at"),
            ("engagement_events", "occurred_at"),
            ("articles", "is_scraped"),
            ("story_reactions", "updated_at"),
        }
        actual_server_defaults = {
            (table.name, column.name)
            for table in Base.metadata.tables.values()
            for column in table.columns
            if column.server_default is not None
        }
        self.assertEqual(actual_server_defaults, expected_server_defaults)
        for model, name in [(Provider, "domain"), (Article, "canonical_url"), (Tag, "name")]:
            self.assertTrue(model.__table__.c[name].unique)
        for table in Base.metadata.tables.values():
            ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
            self.assertIn("PRIMARY KEY", ddl)
            for fk in table.foreign_keys:
                expected = "SET NULL" if table.name == "engagement_events" and fk.parent.name != "event_type" else (
                    None if table.name in ("articles", "engagement_events") else "CASCADE"
                )
                self.assertEqual(fk.ondelete, expected)
        for model, columns in [(StoryArticle, ["story_id", "article_id"]),
                               (StoryTag, ["story_id", "tag_id"]),
                               (UserTag, ["user_id", "tag_id"]),
                               (StoryReaction, ["user_id", "story_id"]),]:
            self.assertEqual(list(model.__table__.primary_key.columns.keys()), columns)


class PersistenceTests(unittest.TestCase):
    def test_story_list_and_detail_response_contract(self):
        from Backend.Dal.repositories.story_repository import StoryRepository
        from Backend.Presentation.schemas.stories import StoryRead, StoryListItem
        story = Story(title="Published story", context="Main content", summary="Summary",
                      status=StoryStatus.published, img_url="https://example.test/image.jpg")
        draft = Story(title="Draft story")
        tag = Tag(name="Science")
        article = Article(provider_id=self.provider.id, canonical_url="https://example.test/story-source",
                          title="Source", content="Source text")
        self.db.add_all([story, draft, tag, article])
        self.db.flush()
        self.db.add(StoryTag(story_id=story.id, tag_id=tag.id, relevance_score=.9))
        self.db.add(StoryArticle(story_id=story.id, article_id=article.id, is_primary=True, similarity_score=1))
        self.db.commit()
        repo = StoryRepository(self.db)
        rows = repo.list(status=StoryStatus.published)
        self.assertEqual(len(rows), 1)
        card = StoryListItem.model_validate(rows[0])
        self.assertEqual(card.articles_count, 1)
        detail = StoryRead.model_validate(repo.get(story.id))
        self.assertEqual(detail.context, "Main content")
        self.assertEqual(detail.tags[0].tag.name, "Science")
        self.assertEqual(detail.articles[0].article.id, article.id)
        self.assertTrue(detail.articles[0].is_primary)
        self.assertEqual(StoryRead.model_validate(repo.get(draft.id)).articles, [])
        self.assertIsNone(repo.get(uuid.uuid4()))
        self.assertEqual(repo.list(status=StoryStatus.published, offset=1), [])

    def test_story_articles_endpoint_data_pagination_count_and_isolation(self):
        from Backend.Dal.repositories.story_repository import StoryRepository
        from Backend.Logic.story_service import StoryService
        from Backend.Presentation.schemas.stories import StoryArticlesPageRead
        first, other, empty = Story(title="First"), Story(title="Other"), Story(title="Empty")
        self.db.add_all([first, other, empty])
        self.db.flush()
        for i in range(3):
            article = Article(provider_id=self.provider.id, canonical_url=f"https://example.test/api/{i}",
                              title=f"Article {i}", content="Full source text" if i != 0 else None)
            self.db.add(article)
            self.db.flush()
            self.db.add(StoryArticle(story_id=first.id if i < 2 else other.id,
                                    article_id=article.id, is_primary=i == 1, similarity_score=.8))
        self.db.commit()
        service = StoryService(StoryRepository(self.db), None, None)
        page = StoryArticlesPageRead.model_validate(service.list_articles(first.id, limit=1))
        self.assertEqual(page.articles_count, 2)
        self.assertEqual(len(page.articles), 1)
        self.assertTrue(page.articles[0].is_primary)
        self.assertEqual(page.articles[0].article.content, "Full source text")
        self.assertEqual(page.articles[0].article.provider.id, self.provider.id)
        self.assertIsNone(service.list_articles(first.id, offset=1).articles[0].article.content)
        self.assertEqual(service.list_articles(first.id, limit=0).articles, [])
        self.assertEqual(service.list_articles(first.id, offset=99).articles_count, 2)
        self.assertEqual(service.list_articles(empty.id).articles_count, 0)
        with self.assertRaises(NotFoundError):
            service.list_articles(uuid.uuid4())

    def setUp(self):
        self.engine = create_engine("sqlite://")
        event.listen(self.engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        # SQLite loses tzinfo; emulate PostgreSQL timestamptz for these local tests.
        def restore_timezone(article, *args):
            for field in ("published_at", "first_seen_at"):
                value = getattr(article, field)
                if value is not None and value.tzinfo is None:
                    from sqlalchemy.orm.attributes import set_committed_value
                    set_committed_value(article, field, value.replace(tzinfo=timezone.utc))
        self.restore_timezone = restore_timezone
        event.listen(Article, "load", restore_timezone)
        event.listen(Article, "refresh", restore_timezone)
        self.provider = Provider(name="Source", domain="example.test", reliability_status="verified")
        self.db.add(self.provider)
        self.db.add(EventWeight(event_type="view", weight=Decimal("1.00")))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        event.remove(Article, "load", self.restore_timezone)
        event.remove(Article, "refresh", self.restore_timezone)
        self.engine.dispose()

    def test_grouping_day_preview_apply_and_publication_fields(self):
        from Backend.jobs.group_day import run
        titles = ["Brand haven Rotterdam", "Brand haven Rotterdam", "Ajax wint wedstrijd"]
        articles = []
        for i, title in enumerate(titles):
            item = Article(provider_id=self.provider.id, canonical_url=f"https://example.test/day/{i}",
                           title=title, description=title, content=title, language="nl",
                           published_at=datetime(2026, 11, 15, 23, i, tzinfo=timezone.utc),
                           first_seen_at=datetime(2026, 11, 16, 1, i, tzinfo=timezone.utc),
                           img_url="https://example.test/photo.jpg" if i == 1 else " ")
            self.db.add(item)
            articles.append(item)
        # Next Amsterdam day: must not be processed.
        self.db.add(Article(provider_id=self.provider.id, canonical_url="https://example.test/next",
                            title=titles[0], description=titles[0], content=titles[0], language="nl",
                            published_at=datetime(2026, 11, 16, 23, tzinfo=timezone.utc)))
        self.db.commit()
        preview = run(self.db, date(2026, 11, 16))
        self.assertEqual(preview["assigned_articles"], 3)
        self.assertFalse(preview["committed"])
        self.assertEqual(self.db.scalars(select(Story)).all(), [])
        result = run(self.db, date(2026, 11, 16), apply=True)
        self.assertEqual(result["assigned_articles"], 3)
        stories = self.db.scalars(select(Story)).all()
        for story in stories:
            primary, = [link.article for link in story.articles if link.is_primary]
            self.assertEqual(story.title, primary.title)
            self.assertEqual(story.context, primary.content)
            self.assertEqual(story.status, StoryStatus.published)
            self.assertIsNotNone(story.first_published_at)
            self.assertEqual(story.img_url, "https://example.test/photo.jpg" if len(story.articles) == 2 else None)
        first_times = {story.id: story.first_published_at for story in stories}
        self.assertEqual(run(self.db, date(2026, 11, 16), apply=True)["assigned_articles"], 0)
        self.assertEqual(first_times, {story.id: story.first_published_at for story in stories})

    def test_dutch_story_grouping_and_retry(self):
        for index, title in enumerate([
            "Brand in haven Rotterdam legt scheepvaart stil",
            "Scheepvaart stil na brand in Rotterdamse haven Rotterdam",
            "Ajax contracteert jonge Spaanse doelman",
        ]):
            self.db.add(Article(provider_id=self.provider.id, canonical_url=f"https://example.test/{index}",
                                title=title, description=title, content=title, language="nl"))
        self.db.commit()
        self.assertEqual(group_articles(self.db), 3)
        self.db.rollback()
        self.assertEqual(self.db.scalars(select(Story)).all(), [])
        self.assertEqual(group_articles(self.db), 3)
        self.db.commit()
        stories = self.db.scalars(select(Story)).all()
        self.assertEqual(sorted(len(s.articles) for s in stories), [1, 2])
        for story in stories:
            primary, = [link for link in story.articles if link.is_primary]
            self.assertEqual(primary.similarity_score, 1)
            self.assertEqual(story.title, primary.article.title)
            self.assertEqual(story.status, StoryStatus.published)
            self.assertEqual(story.context, primary.article.content)
            self.assertIsNotNone(story.first_published_at)
        self.assertEqual(group_articles(self.db), 0)

    def test_grouping_limits_complete_articles_before_loading(self):
        for index, missing in enumerate([None, "", " \t\n", "complete", "complete", "complete"]):
            self.db.add(Article(
                provider_id=self.provider.id, canonical_url=f"https://example.test/limit/{index}",
                title="Brand haven Rotterdam", description="Brand haven Rotterdam",
                content=missing, language="nl",
            ))
        self.db.commit()
        self.assertEqual(group_articles(self.db, limit=2), 2)
        self.db.commit()
        self.assertEqual(group_articles(self.db, limit=2), 1)
        self.db.commit()
        self.assertEqual(group_articles(self.db, limit=2), 0)

    def test_provider_sources_relationship_defaults_and_cascade(self):
        self.provider.sources = [
            ProviderSource(name="Headlines", source_type="rss", url="https://example.test/news"),
            ProviderSource(name="Sport", source_type="rss", url="https://example.test/sport"),
        ]
        self.db.commit()
        self.db.expire_all()
        self.assertEqual({source.name for source in self.provider.sources}, {"Headlines", "Sport"})
        for source in self.provider.sources:
            self.assertIs(source.provider, self.provider)
            self.assertEqual(source.poll_interval_minutes, 60)
            self.assertTrue(source.is_active)
            self.assertEqual(source.configuration, {})

        # Bypass ORM deletion to exercise the database foreign-key cascade.
        self.db.execute(text("DELETE FROM providers WHERE id = :id"), {"id": self.provider.id.hex})
        self.assertEqual(self.db.scalars(select(ProviderSource.id)).all(), [])

    def test_user_bootstrap_preserves_identity_preferences_and_consent(self):
        repo = UserRepository(self.db)
        subject = str(uuid.uuid4())
        self.assertIsNone(repo.get_by_identity("supabase", subject))
        first = repo.get_or_create_by_identity("supabase", subject)
        self.assertFalse(first.analytics_consent)
        self.assertFalse(UserRead.model_validate(first).onboarding_completed)
        repo.update(first, onboarding_completed=True)
        consent_time = datetime.now(timezone.utc)
        repo.update(first, language="en", preferences={"theme": "dark"},
                    analytics_consent=True, consent_updated_at=consent_time)
        event_id = uuid.uuid4()
        self.db.add(EngagementEvent(id=event_id, user_id=first.id, session_id=uuid.uuid4(),
                                    event_type="view", ingested_at=consent_time))
        self.db.commit()
        self.db.close()
        self.db = Session(self.engine, expire_on_commit=False)
        repo = UserRepository(self.db)
        again = repo.get_or_create_by_identity("supabase", subject)
        self.db.commit()
        self.assertEqual(again.id, first.id)
        self.assertEqual(self.db.get(EngagementEvent, event_id).user_id, again.id)
        self.assertTrue(UserRead.model_validate(again).onboarding_completed)
        self.assertEqual(again.language, "en")
        self.assertEqual(again.preferences, {"theme": "dark"})
        self.assertTrue(again.analytics_consent)
        self.assertIsNotNone(again.consent_updated_at)
        self.assertEqual(repo.get_by_identity("supabase", subject).id, first.id)
        self.assertIsNone(repo.get_by_identity("google", subject))
        rows = list(self.db.scalars(select(User).where(User.auth_subject == subject)))
        self.assertEqual(len(rows), 1)

    def test_ingestion_keeps_latest_publisher_update(self):
        repo = ArticleRepository(self.db)
        fields = dict(provider_id=self.provider.id, canonical_url="https://example.test/update", title="News")
        first, _ = repo.ingest(**fields)
        self.assertIsNone(first.last_updated_at)
        older = datetime(2025, 1, 1, tzinfo=timezone.utc)
        newer = datetime(2025, 1, 2, tzinfo=timezone.utc)
        for incoming in (older, newer, None, older):
            result, _ = repo.ingest(**fields, last_updated_at=incoming)
        # SQLite returns naive datetimes for timezone-aware columns.
        self.assertEqual(result.last_updated_at.replace(tzinfo=timezone.utc), newer)

    def test_ingestion_preserves_identity_and_non_null_content(self):
        repo = ArticleRepository(self.db)
        first, created = repo.ingest(provider_id=self.provider.id, canonical_url="https://example.test/a",
                                     title="Initial", description="Keep me")
        self.assertTrue(created)
        self.db.commit()
        original_id, first_seen = first.id, first.first_seen_at
        updated, created = repo.ingest(provider_id=self.provider.id, canonical_url=first.canonical_url,
                                       title="Refreshed", description=None)
        self.db.commit()
        self.assertFalse(created)
        self.assertEqual(updated.id, original_id)
        self.assertEqual(updated.first_seen_at, first_seen)
        self.assertEqual(updated.title, "Refreshed")
        self.assertEqual(updated.description, "Keep me")
        self.assertEqual(len(self.db.scalars(select(Article)).all()), 1)
        self.assertIsNotNone(updated.last_seen_at)

    def test_deletion_retains_events_and_removes_associations(self):
        for parent_kind in ("user", "story", "article", "tag"):
            for loaded in (False, True):
                with self.subTest(parent=parent_kind, loaded=loaded):
                    user = User(auth_provider="test", auth_subject=str(uuid.uuid4()))
                    story, tag = Story(title="Story"), Tag(name=str(uuid.uuid4()))
                    article = Article(provider_id=self.provider.id, canonical_url=str(uuid.uuid4()), title="Article")
                    self.db.add_all([user, story, tag, article])
                    self.db.flush()
                    self.db.add_all([
                        UserTag(user_id=user.id, tag_id=tag.id, is_declared=True, score=0.0),
                        StoryTag(story_id=story.id, tag_id=tag.id),
                        StoryArticle(story_id=story.id, article_id=article.id),
                    ])
                    engagement = EngagementEvent(user_id=user.id, story_id=story.id, article_id=article.id,
                                                 session_id=uuid.uuid4(), event_type="view",
                                                 ingested_at=datetime.now(timezone.utc))
                    self.db.add(engagement)
                    self.db.commit()
                    parent = {"user": user, "story": story, "article": article, "tag": tag}[parent_kind]
                    if loaded:
                        for relation in inspect(type(parent)).relationships:
                            getattr(parent, relation.key)
                    if parent_kind == "user":
                        UserRepository(self.db).delete(parent)
                    else:
                        self.db.delete(parent)
                    self.db.commit()
                    self.db.expire_all()
                    retained = self.db.get(EngagementEvent, engagement.id)
                    self.assertIsNotNone(retained)
                    if parent_kind != "tag":
                        self.assertIsNone(getattr(retained, parent_kind + "_id"))
                    associations = {
                        "user": [(UserTag, "user_id", user.id)],
                        "story": [(StoryTag, "story_id", story.id), (StoryArticle, "story_id", story.id)],
                        "article": [(StoryArticle, "article_id", article.id)],
                        "tag": [(StoryTag, "tag_id", tag.id), (UserTag, "tag_id", tag.id)],
                    }
                    for model, field, value in associations[parent_kind]:
                        self.assertIsNone(self.db.scalars(select(model).where(getattr(model, field) == value)).first())

    def test_server_defaults_without_orm_defaults(self):
        # Raw SQL proves these defaults are supplied by the database.
        story_id, user_id = uuid.uuid4().hex, uuid.uuid4().hex
        self.db.execute(text("INSERT INTO stories (id, title) VALUES (:id, 'New')"), {"id": story_id})
        self.db.execute(text("INSERT INTO users (id, auth_provider, auth_subject) VALUES (:id, 'test', :id)"), {"id": user_id})
        story = self.db.get(Story, uuid.UUID(story_id))
        user = self.db.get(User, uuid.UUID(user_id))
        self.assertEqual(story.status, StoryStatus.draft)
        self.assertIsNotNone(story.last_updated_at)
        self.assertFalse(user.analytics_consent)

    def test_auth_identity_and_domain_mapping(self):
        payload = UserCreate(auth_provider="test", auth_subject="subject").model_dump()
        repo = UserRepository(self.db)
        user = repo.add(**payload)
        self.assertEqual(repo.get(user.id).auth_subject, "subject")
        self.assertIsNone(UserRead.model_validate(user).affinity_updated_at)
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                repo.add(**payload)
        repo.add(auth_provider="another", auth_subject="subject")

    def test_tag_selection_preserves_affinity(self):
        repo = UserRepository(self.db)
        user = repo.add(auth_provider="test", auth_subject="tags")
        tag = Tag(name="science")
        self.db.add(tag)
        self.db.flush()
        repo.replace_tags(user, [tag.id])
        row = self.db.get(UserTag, (user.id, tag.id))
        self.assertTrue(row.is_declared)
        self.assertEqual(row.score, 0.0)
        row.score = 2.5
        row.computed_at = datetime.now(timezone.utc)
        self.db.flush()
        repo.replace_tags(user, [])
        self.assertFalse(row.is_declared)
        self.assertEqual(row.score, 2.5)
        self.assertEqual(repo.get_tag_ids(user.id), [])
        repo.replace_tags(user, [tag.id])
        self.assertTrue(row.is_declared)
        self.assertEqual(row.score, 2.5)
        self.assertIsNotNone(row.computed_at)

    def test_event_receipt_time_and_valid_type(self):
        repo = EngagementEventRepository(self.db)
        recorded = repo.add(session_id=uuid.uuid4(), event_type="view")
        self.assertIsNotNone(recorded.ingested_at)
        self.assertEqual(EngagementEventRead.model_validate(recorded).ingested_at, recorded.ingested_at)
        with self.assertRaises(NotFoundError):
            repo.add(session_id=uuid.uuid4(), event_type="unknown")
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.add(EngagementEvent(session_id=uuid.uuid4(), event_type="unknown",
                                            ingested_at=datetime.now(timezone.utc)))
                self.db.flush()
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.add(EngagementEvent(session_id=uuid.uuid4(), event_type="view"))
                self.db.flush()
    def test_story_reaction_constraints_and_cascade(self):
        user = User(
            auth_provider="test",
            auth_subject=str(uuid.uuid4()),
        )
        story = Story(title="Reaction test")

        self.db.add_all([user, story])
        self.db.flush()

        user_id = user.id
        story_id = story.id

        self.db.add(
            StoryReaction(
                user_id=user_id,
                story_id=story_id,
                reaction="like",
            )
        )
        self.db.flush()

        saved = self.db.get(
            StoryReaction,
            (user_id, story_id),
        )

        self.assertEqual(saved.reaction, "like")
        self.assertIsNotNone(saved.updated_at)

        # Only one reaction per user/story pair.
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.execute(
                    StoryReaction.__table__.insert().values(
                        user_id=user_id,
                        story_id=story_id,
                        reaction="dislike",
                    )
                )

        # Reject values outside the allowed choices.
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.execute(
                    StoryReaction.__table__.update()
                    .where(
                        StoryReaction.user_id == user_id,
                        StoryReaction.story_id == story_id,
                    )
                    .values(reaction="invalid")
                )

        # Deleting the story also deletes its reaction.
        self.db.delete(story)
        self.db.flush()

        remaining = self.db.execute(
            select(StoryReaction.__table__).where(
                StoryReaction.user_id == user_id,
                StoryReaction.story_id == story_id,
            )
        ).first()

        self.assertIsNone(remaining)

if __name__ == "__main__":
    unittest.main()
