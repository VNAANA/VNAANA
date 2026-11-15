"""Seed three draft Stories for Genre Classification development.

This utility is intentionally dry-run by default. It never imports
``Backend.database`` and therefore cannot fall back to the application's local
database URL. See ``Backend/GENRE_CLASSIFICATION_MOCK_STORIES.md`` before using
``--apply`` or ``--cleanup``.
"""

from __future__ import annotations

import argparse
import os
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from Backend.Dal.models import Story as StoryModel
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.story_repository import StoryRepository
from Backend.Dal.repositories.tag_repository import TagRepository
from Backend.Logic.domain.story import StoryStatus
from Backend.Logic.story_service import StoryService


ID_NAMESPACE = uuid.UUID("8b055cad-dfc9-4c8a-9417-e321dc35d642")
TITLE_PREFIX = "[GC TEST]"
ALLOWED_ENVIRONMENTS = {"test", "development"}


@dataclass(frozen=True)
class StoryFixture:
    key: str
    title: str
    summary: str
    context: str
    source_url: str
    source_published_on: date

    @property
    def id(self) -> uuid.UUID:
        return uuid.uuid5(ID_NAMESPACE, self.key)

    def story_fields(self) -> dict:
        return {
            "id": self.id,
            "title": f"{TITLE_PREFIX} {self.title}",
            "summary": self.summary,
            "context": self.context,
            "status": StoryStatus.draft,
        }


FIXTURES = (
    StoryFixture(
        key="climate-dutch-government-policy",
        title="Klimaatdoel 2030 raakt verder uit zicht door kabinetsbeleid",
        summary=(
            "Het PBL acht de kans zeer klein dat Nederland met het huidige "
            "beleid het wettelijke klimaatdoel voor 2030 haalt. Geschrapte en "
            "versoepelde maatregelen beperken de extra daling van de uitstoot."
        ),
        context=(
            "De Klimaatwet vraagt in 2030 om 55 procent minder uitstoot dan in "
            "1990. De raming zet de keuzes van het kabinet, industriebeleid en "
            "de uitvoerbaarheid van aanvullend klimaatbeleid centraal."
        ),
        source_url=(
            "https://nos.nl/collectie/13871/artikel/2582721-klimaatdoel-met-"
            "huidig-beleid-niet-gehaald-van-vooruitkijken-nauwelijks-meer-sprake"
        ),
        source_published_on=date(2025, 9, 16),
    ),
    StoryFixture(
        key="culture-film-rereleases",
        title="Klassieke filmhits keren steeds vaker terug in de bioscoop",
        summary=(
            "Nederlandse bioscopen vertonen steeds meer heruitgaven van bekende "
            "films. Distributeurs zien dat publiek opnieuw belangstelling heeft "
            "voor oudere titels op het grote doek."
        ),
        context=(
            "De terugkeer van onder meer Jaws past in een bredere groei van "
            "filmklassiekers die opnieuw worden uitgebracht. De ontwikkeling "
            "raakt zowel filmcultuur als de commerciële bioscoopsector."
        ),
        source_url=(
            "https://nos.nl/artikel/2580272-filmhits-uit-verleden-terug-op-het-"
            "witte-doek-mensen-willen-geen-klonen-meer"
        ),
        source_published_on=date(2025, 8, 28),
    ),
    StoryFixture(
        key="international-politics-european-leadership",
        title="Koning benadrukt Europees leiderschap in onrustige wereldpolitiek",
        summary=(
            "Koning Willem-Alexander pleit voor een sterke Europese Unie in een "
            "periode van internationale onzekerheid. Hij koppelt Europees "
            "leiderschap aan vrede en samenwerking rond Oekraïne en het Midden-Oosten."
        ),
        context=(
            "De uitspraken vielen tijdens een staatsbezoek aan Cyprus en tegen "
            "de achtergrond van het Nederlandse debat over steun aan Oekraïne, "
            "Europese samenwerking en de komende NAVO-top."
        ),
        source_url=(
            "https://nos.nl/artikel/2558298-koning-over-internationale-politiek-"
            "nederland-neemt-rol-in-leiderschap"
        ),
        source_published_on=date(2025, 3, 5),
    ),
)


def _safe_target(url: URL) -> str:
    host = url.host or ""
    database = (url.database or "").lstrip("/")
    if not host or not database:
        raise RuntimeError("The database URL must include an explicit host and database name")
    return f"{host}/{database}"


def _verified_database_url(confirm_target: str) -> URL:
    raw_url = os.getenv("GENRE_CLASSIFICATION_DATABASE_URL")
    environment = os.getenv("GENRE_CLASSIFICATION_DATABASE_ENV", "").lower()
    expected_host = os.getenv("GENRE_CLASSIFICATION_EXPECTED_DB_HOST")
    expected_database = os.getenv("GENRE_CLASSIFICATION_EXPECTED_DB_NAME")

    if not raw_url:
        raise RuntimeError("GENRE_CLASSIFICATION_DATABASE_URL is required; no fallback is allowed")
    if environment not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            "GENRE_CLASSIFICATION_DATABASE_ENV must be 'test' or 'development'"
        )
    if not expected_host or not expected_database:
        raise RuntimeError(
            "GENRE_CLASSIFICATION_EXPECTED_DB_HOST and "
            "GENRE_CLASSIFICATION_EXPECTED_DB_NAME are required"
        )

    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Genre Classification fixtures require PostgreSQL")
    if url.host != expected_host or (url.database or "").lstrip("/") != expected_database:
        raise RuntimeError("The database URL does not match the separately confirmed target")

    target = _safe_target(url)
    if confirm_target != target:
        raise RuntimeError(f"Pass --confirm-target {target!r} to acknowledge the exact target")
    return url


def _same_fixture(existing, fixture: StoryFixture) -> bool:
    fields = fixture.story_fields()
    return all(getattr(existing, name) == value for name, value in fields.items() if name != "id")


def _apply(session: Session) -> tuple[int, int]:
    repository = StoryRepository(session)
    service = StoryService(
        stories=repository,
        articles=ArticleRepository(session),
        tags=TagRepository(session),
    )
    created = skipped = 0

    for fixture in FIXTURES:
        existing = repository.get(fixture.id)
        if existing is not None:
            if not _same_fixture(existing, fixture):
                raise RuntimeError(
                    f"Story ID {fixture.id} exists but does not match fixture {fixture.key!r}"
                )
            skipped += 1
            continue
        service.create_story(fixture.story_fields())
        created += 1

    return created, skipped


def _cleanup(session: Session) -> int:
    fixture_ids = [fixture.id for fixture in FIXTURES]
    rows = list(session.scalars(select(StoryModel).where(StoryModel.id.in_(fixture_ids))))
    for row in rows:
        if not row.title.startswith(f"{TITLE_PREFIX} "):
            raise RuntimeError(f"Refusing to delete non-fixture Story {row.id}")
        session.delete(row)
    return len(rows)


def _print_fixtures() -> None:
    print("Dry run only; no database was opened.\n")
    for fixture in FIXTURES:
        print(f"{fixture.id}  {fixture.story_fields()['title']}")
        print(f"  Source: {fixture.source_published_on.isoformat()}  {fixture.source_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="create missing fixtures")
    action.add_argument("--cleanup", action="store_true", help="delete only these fixtures")
    parser.add_argument(
        "--confirm-target",
        default="",
        help="exact host/database confirmation required for a write",
    )
    args = parser.parse_args()

    if not args.apply and not args.cleanup:
        _print_fixtures()
        return

    url = _verified_database_url(args.confirm_target)
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with Session(engine) as session, session.begin():
            if args.apply:
                created, skipped = _apply(session)
                print(f"Created {created} fixture(s); {skipped} already matched.")
            else:
                deleted = _cleanup(session)
                print(f"Deleted {deleted} Genre Classification fixture(s).")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
