import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from Backend.jobs import run_news_pipeline as pipeline


@pytest.fixture
def pipeline_mocks(monkeypatch):
    events = []
    db = Mock()
    db.commit.side_effect = lambda: events.append("commit")

    session_factory = Mock(return_value=db)
    monkeypatch.setattr(pipeline, "SessionLocal", session_factory)

    for name in (
        "ArticleRepository",
        "ProviderRepository",
        "ProviderSourceRepository",
        "StoryRepository",
        "ProviderSourceService",
        "ArticleService",
        "ArticleNormalizationService",
        "RSSSource",
    ):
        monkeypatch.setattr(pipeline, name, Mock())

    gathering_service = Mock()
    gathering_service.gather = AsyncMock()
    monkeypatch.setattr(
        pipeline,
        "NewsGatheringService",
        Mock(return_value=gathering_service),
    )

    scraping_service = Mock()
    scraping_service.scrape_pending_articles.return_value = {
        "total": 0,
        "successful": 0,
        "failed": 0,
    }
    monkeypatch.setattr(
        pipeline,
        "ArticleScrapingService",
        Mock(return_value=scraping_service),
    )

    cleanup_service = Mock()
    cleanup_service.delete_expired.return_value = {
        "stories": 0,
        "articles": 0,
    }
    monkeypatch.setattr(
        pipeline,
        "CleanupService",
        Mock(return_value=cleanup_service),
    )

    state = SimpleNamespace(enabled=False, stories=[])

    def group_articles(db, *, report):
        events.append("group")
        report({"stories": state.stories})
        return len(state.stories)

    monkeypatch.setattr(pipeline, "group_articles", Mock(side_effect=group_articles))
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        Mock(side_effect=lambda: SimpleNamespace(
            genre_classification_pipeline_enabled=state.enabled,
        )),
    )

    classifier = Mock(return_value={"processed": {}, "skipped": {}, "failed": {}})
    monkeypatch.setattr(pipeline, "classify_grouped_stories", classifier)

    return SimpleNamespace(
        db=db,
        events=events,
        state=state,
        classifier=classifier,
        session_factory=session_factory,
    )


@pytest.mark.parametrize(
    ("enabled", "stories"),
    [
        (False, [{"id": "story-disabled"}]),
        (True, []),
    ],
)
def test_pipeline_skips_classification_when_disabled_or_no_stories(
    pipeline_mocks, caplog, enabled, stories,
):
    pipeline_mocks.state.enabled = enabled
    pipeline_mocks.state.stories = stories
    caplog.set_level(logging.INFO, logger=pipeline.__name__)

    pipeline.main()

    pipeline_mocks.classifier.assert_not_called()
    assert "News pipeline completed successfully" in caplog.text
    assert pipeline_mocks.db.commit.call_count == 4
    pipeline_mocks.db.rollback.assert_not_called()
    pipeline_mocks.db.close.assert_called_once_with()


def test_pipeline_classifies_reported_stories_after_grouping_commit(
    pipeline_mocks, caplog,
):
    pipeline_mocks.state.enabled = True
    pipeline_mocks.state.stories = [
        {"id": "created-story"},
        {"id": "updated-story"},
    ]

    def classify(story_ids, *, session_factory):
        pipeline_mocks.events.append("classify")
        return {"processed": {}, "skipped": {}, "failed": {}}

    pipeline_mocks.classifier.side_effect = classify
    caplog.set_level(logging.INFO, logger=pipeline.__name__)

    pipeline.main()

    pipeline_mocks.classifier.assert_called_once_with(
        ["created-story", "updated-story"],
        session_factory=pipeline_mocks.session_factory,
    )
    assert pipeline_mocks.events[-3:] == ["group", "commit", "classify"]
    assert "processed=0 skipped=0 failed=0" in caplog.text
    assert "News pipeline completed successfully" in caplog.text


def test_pipeline_logs_classification_result_counts(pipeline_mocks, caplog):
    pipeline_mocks.state.enabled = True
    pipeline_mocks.state.stories = [{"id": "story-with-result"}]
    pipeline_mocks.classifier.return_value = {
        "processed": {"saved": "saved"},
        "skipped": {"tagged": "already_tagged", "changed": "changed"},
        "failed": {"failed-1": "inference failed", "failed-2": "tag write failed"},
    }
    caplog.set_level(logging.INFO, logger=pipeline.__name__)

    pipeline.main()

    assert "processed=1 skipped=2 failed=2" in caplog.text
    assert "News pipeline completed successfully" in caplog.text
    pipeline_mocks.db.rollback.assert_not_called()


def test_pipeline_logs_unexpected_classification_error_and_completes(
    pipeline_mocks, caplog,
):
    pipeline_mocks.state.enabled = True
    pipeline_mocks.state.stories = [{"id": "story-with-error"}]
    pipeline_mocks.classifier.side_effect = RuntimeError("unexpected failure")
    caplog.set_level(logging.INFO, logger=pipeline.__name__)

    pipeline.main()

    assert "Genre classification failed" in caplog.text
    assert "unexpected failure" in caplog.text
    assert "News pipeline completed successfully" in caplog.text
    pipeline_mocks.db.rollback.assert_not_called()
    pipeline_mocks.db.close.assert_called_once_with()
