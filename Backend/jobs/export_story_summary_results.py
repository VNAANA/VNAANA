import csv
from pathlib import Path

from Backend.jobs.summarize_grouped_stories import RESULTS, iter_results, read_result

FIELDS = (
    "story_id", "story_title", "article_ids", "publishers", "article_count",
    "provider", "model", "prompt_version", "input_sha256", "generated_summary",
    "generation_time_seconds", "generation_status", "database_status", "database_verification", "error",
    "review_status", "review_notes", "result_file",
)


def export_results(results: Path, output: Path) -> int:
    reviews = {}
    if output.exists():
        with output.open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                reviews[row["result_file"]] = (row["review_status"], row["review_notes"])

    rows = []
    for path, record in iter_results(results):
        articles = record.get("articles")
        if articles is not None and (
            not isinstance(articles, list)
            or not all(isinstance(article, dict) and all(
                article.get(key) is None or isinstance(article[key], str)
                for key in ("article_id", "publisher")
            ) for article in articles)
        ):
            print(f"Invalid Article metadata in result: {path.name}")
            continue
        review_status, review_notes = reviews.get(path.name, ("", ""))
        row = {key: record.get(key) for key in FIELDS}
        row.update(
            article_ids=";".join(a["article_id"] for a in articles or [] if a.get("article_id")),
            publishers=";".join(dict.fromkeys(a["publisher"] for a in articles or [] if a.get("publisher"))),
            article_count=len(articles) if articles is not None else None,
            generated_summary=record.get("summary"),
            generation_time_seconds=record.get("elapsed_seconds"),
            generation_status=record.get("status"),
            error=record.get("error") or record.get("reason") or (
                record.get("database_reason") if record.get("database_status") in {"failed", "skipped"} else None
            ),
            review_status=review_status,
            review_notes=review_notes,
            result_file=path.name,
        )
        reconciliation = path.with_suffix(".reconciliation.json")
        if reconciliation.exists():
            checked = read_result(reconciliation) or {}
            if checked.get("outcome") == "confirmed_saved":
                row.update(database_status="saved", database_verification="matched", error=None)
            elif checked.get("outcome") in {"different_summary", "not_stored"}:
                row["database_verification"] = checked["outcome"]
        rows.append(row)

    temporary = output.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)
    return len(rows)


def main() -> None:
    output = RESULTS.parent / "story_summary_evaluation.csv"
    count = export_results(RESULTS, output)
    print(f"Exported {count} attempts to {output}")


if __name__ == "__main__":
    main()
