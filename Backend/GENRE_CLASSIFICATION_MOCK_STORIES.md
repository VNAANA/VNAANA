# Genre Classification mock Stories

These three Dutch fixtures are deliberately short, original paraphrases of
verified news reports. No full article text is stored in Git. They exercise
different classifier labels while using the existing `Story` fields only.

| Fixture | Intended coverage | Source and publication date |
|---|---|---|
| Climate and Dutch policy | Climate, Domestic, Politics | [NOS: Klimaatdoel met huidig beleid niet gehaald](https://nos.nl/collectie/13871/artikel/2582721-klimaatdoel-met-huidig-beleid-niet-gehaald-van-vooruitkijken-nauwelijks-meer-sprake), 16 September 2025 |
| Film rereleases | Culture, Entertainment | [NOS: Filmhits uit verleden terug op het witte doek](https://nos.nl/artikel/2580272-filmhits-uit-verleden-terug-op-het-witte-doek-mensen-willen-geen-klonen-meer), 28 August 2025 |
| European leadership | International, Politics | [NOS: Koning over internationale politiek](https://nos.nl/artikel/2558298-koning-over-internationale-politiek-nederland-neemt-rol-in-leiderschap), 5 March 2025 |

The intended labels document why each fixture exists; the seed script does
not write those labels to `story_tags`. Classification output must remain the
thing under test.

## Existing architecture

`Backend/seed_genre_classification_stories.py` constructs the existing
`StoryRepository`, `ArticleRepository`, `TagRepository`, and `StoryService`
with one SQLAlchemy session. Creation goes through `StoryService.create_story`.
Every fixture has `status=draft`, so it is excluded from the published-story
recommendation candidates.

The source URL and date are fixture documentation only because the current
`Story` model has no source fields. They are not inserted into the database.

## Safety contract

Running the script without an action is a dry run and never creates an engine.
Writes require all of the following to be supplied explicitly:

- `GENRE_CLASSIFICATION_DATABASE_URL` (there is no localhost fallback);
- `GENRE_CLASSIFICATION_DATABASE_ENV`, exactly `test` or `development`;
- `GENRE_CLASSIFICATION_EXPECTED_DB_HOST`;
- `GENRE_CLASSIFICATION_EXPECTED_DB_NAME`;
- `--confirm-target`, exactly matching the parsed `host/database` target.

The database owner must verify that the host and database identify an approved
isolated test/development database before these values are configured. Do not
place credentials in this document, source control, shell history, or chat.

No Alembic migration is needed: these fixtures use the current `stories`
schema. Do not run this script until the target database is confirmed to have
the existing schema.

## Idempotency and cleanup

Fixture UUIDs are deterministic UUID5 values derived from stable fixture keys.
Applying the seed repeatedly skips exact matches. If a matching UUID contains
different data, the transaction aborts instead of overwriting it.

Cleanup targets only those three UUIDs and additionally requires the
`[GC TEST]` title prefix. Deleting a fixture uses existing ORM cascade behavior
for any later StoryTag links. Apply and cleanup each run in a single transaction,
so an error rolls back the whole operation.
