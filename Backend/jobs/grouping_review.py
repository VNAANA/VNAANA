"""Human-readable grouping diagnostics and a JSON sample for manual labeling."""

import json
from pathlib import Path

from Backend.Logic.story_grouping import assess_story, cosine, MIN_SCORE, MIN_MARGIN

LABELS = ["same event", "same topic but different event", "unrelated"]


def article_details(article):
    return {
        "id": str(article.id),
        "headline": article.title,
        "provider": article.provider.name,
        "url": article.canonical_url,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "first_seen_at": article.first_seen_at.isoformat(),
    }


def display_article(details):
    timestamp = details["published_at"] or details["first_seen_at"] + " (first seen fallback)"
    print(f"  {details['headline']} | {details['provider']} | {timestamp}")
    print(f"  {details['url']}")


def preview_review(groups, vectors, touched, decisions, *, output=None):
    accepted = []
    singletons = []
    no_candidates = 0
    # Stable ordering makes the preview and sample easy to compare between runs.
    ordered = sorted(touched, key=lambda key: str(groups[key][0].id))
    for story_id in ordered:
        primary, members = groups[story_id]
        print(f"\nSTORY | {primary.title} | {len(members)} articles")
        for member in sorted(members, key=lambda article: str(article.id)):
            score = cosine(vectors[primary.id], vectors[member.id])
            print(f"  {'primary' if member.id == primary.id else 'source'} | {score:.3f}")
            display_article(article_details(member))
            if member.id != primary.id and member.title.casefold().strip() != primary.title.casefold().strip():
                accepted.append({
                    "kind": "accepted link", "score": round(score, 6),
                    "article": article_details(member), "comparison": article_details(primary),
                    "label": "", "notes": "",
                })
        if len(members) != 1:
            continue
        candidates = {key: value for key, value in groups.items() if key != story_id}
        assessment = assess_story(primary, candidates, vectors)
        print(f"  Original assignment reason: {decisions[primary.id]}")
        reason = assessment["reason"]
        if reason == "accepted":
            reason = "would match after batch; candidate or primary changed since assignment"
        print(f"  Final-batch comparison: {reason}")
        scores = assessment["scores"]
        if not scores:
            no_candidates += 1
            continue
        score, nearest_id = scores[0]
        nearest = groups[nearest_id][0]
        runner_up = scores[1][0] if len(scores) > 1 else None
        print(f"  Nearest eligible story | {score:.3f} | runner-up score: {runner_up}")
        display_article(article_details(nearest))
        singletons.append({
            "kind": "singleton nearest match", "score": round(score, 6),
            "reason": reason, "original_reason": decisions[primary.id],
            "runner_up_score": runner_up,
            "article": article_details(primary), "comparison": article_details(nearest),
            "label": "", "notes": "",
        })

    # Deliberately inspect the weakest accepted links and strongest missed links.
    # This is a diagnostic sample, not an unbiased estimate of overall accuracy.
    accepted.sort(key=lambda row: (row["score"], row["article"]["id"]))
    singletons.sort(key=lambda row: (-row["score"], row["article"]["id"]))
    sample = accepted[:20] + singletons[:20]
    print(f"\nReview sample: {min(20, len(accepted))} accepted pairs, "
          f"{min(20, len(singletons))} singleton pairs.")
    print(f"Singletons without an eligible comparison: {no_candidates}.")
    print("Compare headlines and opening paragraphs, then choose a label: " + ", ".join(LABELS))
    if output:
        Path(output).write_text(json.dumps({
            "threshold": MIN_SCORE, "minimum_margin": MIN_MARGIN,
            "selection": "weakest accepted links and strongest singleton candidates",
            "allowed_labels": LABELS, "pairs": sample,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Review sample written to {output}. Fill in label and notes for each pair.")
    return sample
