# Adding AI after story grouping

This is guidance for ai smmarization and tag classification to connect
to the news pipeline.

## Where to add the AI call

Open [`run_news_pipeline.py`](run_news_pipeline.py), inside `main()`, around
lines **114–116**. Find:

```python
assigned = group_articles(db)
db.commit()
logger.info("News pipeline completed successfully: %s articles grouped", assigned)
```

Add the AI step after this commit and before the completion log. Grouping must
finish saving stories before AI starts. The resulting order should be:

```text
Gather news → scrape content → cleanup → group stories → commit → AI → completion log
```

## How to pass the story IDs

`group_articles()` returns an article count, not story IDs. Its existing `report`
callback can provide the stories created or updated in this run:

```python
report = {}
assigned = group_articles(db, report=report.update)
db.commit()

story_ids = [row["id"] for row in report.get("stories", [])]

# Import and call your own AI function here, passing story_ids.
# Example only: process_stories_with_ai(story_ids)

logger.info("News pipeline completed successfully: %s articles grouped", assigned)
```

`process_stories_with_ai` is an example name, **not an existing function**.

## Where the AI code belongs

1. Put model configuration in `Backend/.env` and expose it through
   [`Backend/config.py`](../config.py). Do not commit credentials.
2. Implement/reuse the AI functions in `Backend/Logic/`. Existing starting points:
   [`ai_service.py`](../Logic/ai_service.py) for summaries and
   [`genre_classification_service.py`](../Logic/genre_classification_service.py)
   for tag classification.
3. Call those functions from the pipeline integration point above. Load models
   once per run, not once for every story. Use DAL repositories for database writes.

## What to save and what to watch for

- Save summary text to `stories.summary`.
- Resolve predicted labels to existing `tags.id`, then save the links and scores
  in `story_tags`. Reuse `GenreClassificationTagAdapter` for label/score validation.
- `stories.context` contains the **primary article's content**. To summarize all
  sources, fetch linked articles through `story_articles` and respect model limits.
- Include updated stories as well as new ones; grouping can add articles to an
  existing story. Do not modify article links or primary selection in the AI step.
- Commit AI output per story. On failure, roll back that story's AI changes and
  report its ID for retry; grouping has already been committed.
- Avoid keeping a database transaction open during model calls. Recheck the
  source before saving if it may have changed while AI was running.
- Decide explicitly whether AI replaces existing tags. `replace_tags()` replaces
  the whole set; an empty set removes all tags.
- Failed stories may not appear in the next grouping report, so keep their IDs
  for a separate retry. Do not log passwords, tokens or full model prompts.

## Azure

If the existing Azure job launches `run_news_pipeline.sh`, an AI call added inside
`main()` will run in the same job after grouping; no second schedule is needed.
Deploy the updated image, configure model settings on the Azure job, and ensure
the model/runtime is available there. Localhost in Azure is not your laptop.
Allow enough execution time and memory for the added AI work.
