"""Run the trained RobBERT V2 classifier against the three mock Stories.

The runner is local-only: it reuses the fixture definitions and the reusable
Genre Classification service. It never imports database configuration.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from Backend.Logic.genre_classification_service import (
    MAX_INPUT_LENGTH,
    MAX_TAGS,
    THRESHOLD,
    GenreClassificationService,
)
from Backend.seed_genre_classification_stories import FIXTURES, TITLE_PREFIX, StoryFixture


def fixture_story(fixture: StoryFixture) -> tuple[str, str | None, str | None]:
    """Return fixture fields while removing the test-only title prefix."""
    fields = fixture.story_fields()
    title = fields["title"]
    prefix = f"{TITLE_PREFIX} "
    if title.startswith(prefix):
        title = title[len(prefix):]
    return title, fields["summary"], fields["context"]


def run(checkpoint: Path, labels_path: Path | None, device_name: str) -> None:
    # Construct once: the same model/tokenizer instance serves every Story.
    service = GenreClassificationService.from_checkpoint(
        checkpoint,
        labels_path=labels_path,
        device_name=device_name,
    )
    print(
        f"Settings: threshold={THRESHOLD:.2f}, max_tags={MAX_TAGS}, "
        f"max_length={MAX_INPUT_LENGTH}, device={service.device}"
    )

    for fixture in FIXTURES:
        title, summary, context = fixture_story(fixture)
        predictions = service.classify(
            title=title,
            summary=summary,
            context=context,
        )
        print(f"\n{title}")
        if not predictions:
            print(f"  No genres at or above {THRESHOLD:.2f}")
            continue
        for prediction in predictions:
            print(f"  {prediction.tag}: {prediction.score:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    checkpoint_from_env = os.getenv("GENRE_CLASSIFICATION_CHECKPOINT")
    labels_from_env = os.getenv("GENRE_CLASSIFICATION_LABELS_FILE")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(checkpoint_from_env) if checkpoint_from_env else None,
        help="local Hugging Face/PyTorch checkpoint directory",
    )
    parser.add_argument(
        "--labels-file",
        type=Path,
        default=Path(labels_from_env) if labels_from_env else None,
        help="optional JSON array giving the checkpoint's trained label order",
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()

    if args.checkpoint is None:
        parser.error("provide --checkpoint or set GENRE_CLASSIFICATION_CHECKPOINT")
    run(args.checkpoint, args.labels_file, args.device)


if __name__ == "__main__":
    main()
