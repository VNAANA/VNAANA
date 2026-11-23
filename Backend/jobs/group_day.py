"""Preview or publish all eligible unlinked articles for one Amsterdam publication day."""

import argparse
import json
from datetime import date
from pathlib import Path

from Backend.Dal.repositories.story_grouping import group_articles
from Backend.Logic.story_grouping import MIN_SCORE, MIN_MARGIN, REPRESENTATIVE_LIMIT


def run(db, publication_day, *, apply=False):
    result = {"mode": "apply" if apply else "preview", "publication_day": publication_day.isoformat(),
              "timezone": "Europe/Amsterdam", "threshold": MIN_SCORE, "minimum_margin": MIN_MARGIN,
              "representative_limit": REPRESENTATIVE_LIMIT, "committed": False}
    try:
        group_articles(db, publication_day=publication_day, limit=None, report=result.update)
        if apply:
            db.commit()
            result["committed"] = True
        else:
            # IDs and publication times for newly created preview stories are provisional.
            for story in result["stories"]:
                if story["created"]:
                    story["first_published_at"] = None
            db.rollback()
    except Exception:
        db.rollback()
        raise
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    # Reserve output before touching the database; never overwrite an earlier review.
    with Path(args.output).open("x", encoding="utf-8") as stream:
        from Backend.database import SessionLocal
        with SessionLocal() as db:
            result = run(db, args.date, apply=args.apply)
        print(f"Assigned {result['assigned_articles']} articles; committed={result['committed']}")
        # If report writing fails after commit, the database transaction remains committed.
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
