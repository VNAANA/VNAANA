import uuid
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from Backend.jobs import classify_grouped_stories as job
from Backend.Logic.domain.story import StoryDetails, StoryStatus, StoryTagDetails
from Backend.Logic.domain.tag import Tag
from Backend.Logic.genre_classification_service import GenrePrediction


class GroupedStoryClassificationTests(TestCase):
    def setUp(self):
        self.open_sessions = 0
        self.tag = Tag(uuid.uuid4(), "Science")
        self.tag_repository = Mock()
        self.tag_repository.get_by_name.side_effect = (
            lambda name: self.tag if name == self.tag.name else None
        )
        self.tag_repository.get_many.return_value = [self.tag]
        self.stories = Mock()
        self.stories.add_genre_tags_if_current.return_value = "saved"
        self.model = Mock()
        self.load = Mock(return_value=self.model)
        self.enterContext(patch.object(job, "StoryRepository", return_value=self.stories))
        self.enterContext(patch.object(job, "TagRepository", return_value=self.tag_repository))
        self.enterContext(patch.object(job, "ArticleRepository"))

    @contextmanager
    def session(self):
        self.open_sessions += 1
        try:
            yield SimpleNamespace(begin=nullcontext)
        finally:
            self.open_sessions -= 1

    def story(self, *, tagged=False):
        return StoryDetails(
            id=uuid.uuid4(), title="A headline", summary=None, context="Article text",
            status=StoryStatus.published, first_published_at=None,
            last_updated_at=datetime.now(timezone.utc),
            tags=[StoryTagDetails(self.tag, Decimal("0.8"))] if tagged else [],
        )

    def classify(self, *ids):
        return job.classify_grouped_stories(
            ids, session_factory=self.session, load_classifier=self.load,
        )

    def test_empty_batch_does_not_load_model_or_open_session(self):
        self.assertEqual(self.classify(), {"processed": {}, "skipped": {}, "failed": {}})
        self.load.assert_not_called()
        self.stories.get.assert_not_called()

    def test_report_ids_are_ordinary_candidates_and_share_one_model(self):
        created, updated = self.story(), self.story()
        self.stories.get.side_effect = [created, updated]

        def predict(**inputs):
            self.assertEqual(self.open_sessions, 0)
            self.assertIsNone(inputs["summary"])
            return [GenrePrediction("Science", 0.8)]

        self.model.classify.side_effect = predict
        result = self.classify(str(created.id), updated.id, created.id)
        self.load.assert_called_once()
        self.assertEqual(self.model.classify.call_count, 2)
        self.assertEqual(set(result["processed"]), {str(created.id), str(updated.id)})
        self.stories.add_genre_tags_if_current.assert_called_with(
            updated, {self.tag.id: Decimal("0.8")},
        )

    def test_existing_tags_and_empty_predictions_skip_writes(self):
        tagged, untagged = self.story(tagged=True), self.story()
        self.stories.get.side_effect = [tagged, untagged]
        self.model.classify.return_value = []
        result = self.classify(tagged.id, untagged.id)
        self.assertEqual(result["skipped"], {
            str(tagged.id): "already_tagged", str(untagged.id): "no predictions",
        })
        self.model.classify.assert_called_once()
        self.stories.add_genre_tags_if_current.assert_not_called()

    def test_changed_content_and_concurrent_tags_are_skipped(self):
        edited, tagged = self.story(), self.story()
        self.stories.get.side_effect = [edited, tagged]
        self.model.classify.return_value = [GenrePrediction("Science", 0.8)]
        self.stories.add_genre_tags_if_current.side_effect = ["changed", "already_tagged"]
        result = self.classify(edited.id, tagged.id)
        self.assertEqual(result["skipped"], {
            str(edited.id): "changed", str(tagged.id): "already_tagged",
        })
        self.stories.replace_tags.assert_not_called()

    def test_missing_vocabulary_and_inference_failure_do_not_stop_batch(self):
        missing, failed, successful = self.story(), self.story(), self.story()
        self.stories.get.side_effect = [missing, failed, successful]
        self.model.classify.side_effect = [
            [GenrePrediction("Science", 0.8), GenrePrediction("Social Issues", 0.7)],
            RuntimeError("private diagnostic"),
            [GenrePrediction("Science", 0.8)],
        ]
        result = self.classify(missing.id, failed.id, successful.id)
        self.assertEqual(result["failed"], {
            str(missing.id): "missing genre in database vocabulary",
            str(failed.id): "inference failed",
        })
        self.assertEqual(result["processed"], {str(successful.id): "saved"})
        self.stories.add_genre_tags_if_current.assert_called_once()
