"""Classify the three database-backed GC test Stories and optionally save tags.

The default transaction is explicitly read-only. Saving requires the seed
script's production and exact-target confirmations.
"""

from __future__ import annotations

import argparse
import os
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from Backend.config import get_settings
from Backend.Dal.models import StoryTag as StoryTagModel
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.story_repository import StoryRepository
from Backend.Dal.repositories.tag_repository import TagRepository
from Backend.Logic.domain.story import StoryStatus
from Backend.Logic.genre_classification_service import GenreClassificationService
from Backend.Logic.genre_classification_tag_adapter import (
    GenreClassificationTagAdapter,
)
from Backend.Logic.story_service import StoryService
from Backend.seed_genre_classification_stories import (
    FIXTURES,
    TITLE_PREFIX,
    _verified_database_url,
)


def run(
    checkpoint: Path,
    *,
    device_name: str,
    apply: bool,
    confirm_target: str,
    confirm_production: bool,
) -> None:
    raw_url = os.getenv("GENRE_CLASSIFICATION_DATABASE_URL")
    if not raw_url:
        raise RuntimeError("GENRE_CLASSIFICATION_DATABASE_URL is required")
    if apply:
        if os.getenv("GENRE_CLASSIFICATION_DATABASE_ENV", "").lower() != "production":
            raise RuntimeError("--apply requires GENRE_CLASSIFICATION_DATABASE_ENV=production")
        url = _verified_database_url(confirm_target, confirm_production)
    else:
        url = make_url(raw_url)
        if not url.drivername.startswith("postgresql"):
            raise RuntimeError("GENRE_CLASSIFICATION_DATABASE_URL must use PostgreSQL")

    classifier = GenreClassificationService.from_checkpoint(
        checkpoint,
        device_name=device_name,
    )
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                if not apply:
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                with Session(bind=connection, autoflush=False) as session:
                    stories = StoryRepository(session)
                    tags = TagRepository(session)
                    adapter = GenreClassificationTagAdapter(tags)
                    service = StoryService(
                        stories=stories,
                        articles=ArticleRepository(session),
                        tags=tags,
                    )

                    for fixture in FIXTURES:
                        story = stories.get(fixture.id)
                        if story is None:
                            raise RuntimeError(f"Fixture Story is missing: {fixture.id}")
                        expected_title = fixture.story_fields()["title"]
                        if story.title != expected_title or story.status != StoryStatus.draft:
                            raise RuntimeError(
                                f"Story {fixture.id} is not the expected draft GC fixture"
                            )

                        prefix = f"{TITLE_PREFIX} "
                        model_title = story.title.removeprefix(prefix)
                        predictions = classifier.classify(
                            title=model_title,
                            summary=story.summary,
                            context=story.context,
                        )
                        resolved = adapter.to_story_tags(predictions)
                        expected = {
                            tag_id: Decimal(str(score))
                            for tag_id, score in resolved.items()
                        }
                        existing_links = session.scalars(
                            select(StoryTagModel).where(
                                StoryTagModel.story_id == story.id
                            )
                        )
                        existing = {
                            link.tag_id: link.relevance_score
                            for link in existing_links
                        }

                        print(f"\n{story.title} ({story.id})")
                        if not predictions:
                            print("  No genres met the classification threshold")
                        for prediction in predictions:
                            tag = tags.get_by_name(prediction.tag)
                            if tag is None:  # The adapter normally raises first.
                                raise RuntimeError(
                                    f"Genre {prediction.tag!r} is missing from the Tag table"
                                )
                            print(
                                f"  {prediction.tag}: {prediction.score:.6f} "
                                f"(tag_id={tag.id})"
                            )

                        if existing:
                            if existing != expected:
                                raise RuntimeError(
                                    f"Refusing to replace unexpected StoryTags for {story.id}; "
                                    f"existing tag IDs={sorted(map(str, existing))}"
                                )
                            print("  StoryTags already match; no write needed")
                        elif apply:
                            service.set_tags(story.id, resolved)
                            print("  StoryTags saved")
                        else:
                            print("  Dry run: StoryTags are empty and ready to save")

                if apply:
                    transaction.commit()
                    print("\nSaved Genre Classification tags for the three fixtures.")
                else:
                    transaction.rollback()
                    print("\nDry run complete; transaction rolled back.")
            except Exception:
                if transaction.is_active:
                    transaction.rollback()
                raise
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    settings = get_settings()
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=settings.genre_classification_model_path,
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default=None,
        help="override GENRE_CLASSIFICATION_DEVICE (default: cpu)",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-target", default="")
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args()
    if args.checkpoint is None:
        parser.error("provide --checkpoint or set GENRE_CLASSIFICATION_MODEL_PATH")
    run(
        args.checkpoint,
        device_name=args.device or settings.genre_classification_device,
        apply=args.apply,
        confirm_target=args.confirm_target,
        confirm_production=args.confirm_production,
    )


if __name__ == "__main__":
    main()
