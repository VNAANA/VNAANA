"""Dutch event grouping using sparse, unit-length TF-IDF vectors."""

import math
import re
from collections import Counter
from zoneinfo import ZoneInfo

STOPWORDS = set(
    "de het een en van in op te met voor aan bij om tot uit naar is zijn was wordt worden door als dat die dit over ook of er na".split()
)
GROUPING_TIMEZONE = ZoneInfo("Europe/Amsterdam")
MIN_SCORE = 0.45
MIN_MARGIN = 0.04
REPRESENTATIVE_LIMIT = 3

BOILERPLATE = (
    "sluiten",
    "al abonnee?",
    "inloggen",
    "ga direct naar inhoud",
    "sluit menu",
    "feitelijke berichtgeving",
    "waargenomen en geverifieerd",
    "kritische en onafhankelijke beoordeling",
    "een terugkerende rubriek",
    "sorry, het lukt niet",
    "probeer de pagina",
    "of probeer het later",
)


def clean_lead(article):
    """Skip navigation, editorial labels and repeated headings before taking the lead."""
    lines = (article.content or "").splitlines()
    usable = []
    for line in lines:
        line = line.strip()
        folded = line.casefold()
        if (
            len(line) < 60
            or folded == article.title.strip().casefold()
            or folded.startswith(BOILERPLATE)
            or folded.startswith("©")
        ):
            continue
        usable.append(line)
    return " ".join(usable)[:800]


def exclusion_reason(article):
    title = article.title.casefold()
    if re.search(r"\b(sudoku|kruiswoordpuzzel|woordzoeker)\b", title):
        return "puzzle page"
    if re.search(r"\brapporten van of voor het ministerie\b", title):
        return "document collection"
    if re.search(r"\bblack friday\b", title) and re.search(
        r"\b(korting\w*|goedkoper|gratis|deals?|aanbieding\w*|euro)\b", title
    ):
        return "shopping promotion"
    if re.match(r"\d{1,2}/\d{1,2} in nieuwsuur:", title):
        return "multi-topic programme listing"
    content = (article.content or "").casefold()
    navigation_count = sum(marker in content for marker in BOILERPLATE[:5])
    if navigation_count >= 3 and not clean_lead(article):
        return "navigation without usable article text"
    return None


def event_conflict(left, right):
    """Conservative checks for known recurring templates, not arbitrary numbers."""
    titles = [article.title.casefold() for article in (left, right)]
    towns = [
        re.search(r"burgemeestersvacature\s+([\w’' -]+)", title) for title in titles
    ]
    if all(towns) and towns[0].group(1).strip() != towns[1].group(1).strip():
        return True
    if all("persconferentie na ministerraad" in title for title in titles):
        dates = [
            re.search(r"\b(\d{1,2}\s+[a-z]+\s+20\d{2})\b", title) for title in titles
        ]
        return all(dates) and dates[0].group(1) != dates[1].group(1)
    return False


def terms(article):
    if exclusion_reason(article):
        return Counter()
    lead = clean_lead(article)
    text = " ".join((article.title, article.title, article.description or "", lead))
    return Counter(
        word
        for word in re.findall(r"[^\W_]+", text.casefold())
        if word not in STOPWORDS
    )


def article_time(article):
    return article.published_at or article.first_seen_at


def article_day(article):
    """Publication day in Amsterdam, falling back to ingestion time."""
    timestamp = article_time(article)
    if timestamp.tzinfo is None:
        raise ValueError("Grouping requires timezone-aware timestamps")
    return timestamp.astimezone(GROUPING_TIMEZONE).date()


def vectors_for(articles):
    documents = {article.id: terms(article) for article in articles}
    frequencies = Counter()
    for counts in documents.values():
        frequencies.update(counts.keys())
    vectors = {}
    for key, counts in documents.items():
        weights = {
            term: count * (1 + math.log((1 + len(documents)) / (1 + frequencies[term])))
            for term, count in counts.items()
        }
        norm = math.sqrt(sum(weight * weight for weight in weights.values()))
        vectors[key] = {term: weight / norm for term, weight in weights.items()}
    return vectors


def cosine(left, right):
    return min(1.0, sum(weight * right.get(term, 0) for term, weight in left.items()))


def _assess_group_candidate(
    article,
    story_id,
    primary,
    members,
    vectors,
    day,
    representative_limit,
):
    """Score one story as a possible match for an article."""
    if not members:
        return "skip", None

    if article_day(primary) != day or any(article_day(m) != day for m in members):
        return "skip", None

    if any(event_conflict(article, member) for member in members):
        return "conflict", None

    ordered = [primary] + [
        m for m in ranked_representatives(members, vectors) if m.id != primary.id
    ]

    candidates = []
    seen = set()

    for member in ordered:
        if len(candidates) >= representative_limit:
            break

        signature = frozenset(vectors[member.id].items())
        if signature not in seen:
            candidates.append(member)
            seen.add(signature)

    comparisons = [
        {
            "article_id": str(member.id),
            "score": cosine(vectors[article.id], vectors[member.id]),
        }
        for member in candidates
    ]

    best = max(comparisons, key=lambda row: row["score"])

    detail = {
        "story_id": str(story_id),
        "score": best["score"],
        "matched_article_id": best["article_id"],
        "representatives": comparisons,
    }

    return "scored", (best["score"], story_id, detail)


def _assessment_reason(scores, conflicts, threshold):
    """Determine why an article was or wasn't assigned to a story."""
    if not scores:
        return (
            "conflicting event location or date"
            if conflicts
            else "no candidate on the same publication day"
        )

    if scores[0][0] < threshold:
        return "below threshold"

    if len(scores) > 1 and scores[0][0] - scores[1][0] < MIN_MARGIN:
        return "too close to the runner-up"

    return "accepted"


def assess_story(
    article,
    groups,
    vectors,
    *,
    representative_limit=REPRESENTATIVE_LIMIT,
    threshold=MIN_SCORE,
):
    """Return the decision and scores for the same candidates used for assignment."""
    scores = []
    candidate_details = {}
    conflicts = []
    day = article_day(article)

    for story_id, (primary, members) in groups.items():
        status, result = _assess_group_candidate(
            article,
            story_id,
            primary,
            members,
            vectors,
            day,
            representative_limit,
        )

        if status == "conflict":
            conflicts.append(story_id)
        elif result is not None:
            score, candidate_id, detail = result
            scores.append((score, candidate_id))
            candidate_details[candidate_id] = detail

    scores.sort(reverse=True)
    reason = _assessment_reason(scores, conflicts, threshold)

    return {
        "reason": reason,
        "scores": scores,
        "score_basis": "Decision-time TF-IDF; candidates available before assignment",
        "threshold": threshold,
        "minimum_margin": MIN_MARGIN,
        "best_candidate": candidate_details[scores[0][1]] if scores else None,
        "runner_up": candidate_details[scores[1][1]] if len(scores) > 1 else None,
        "score_gap": scores[0][0] - scores[1][0] if len(scores) > 1 else None,
    }


def choose_story(
    article,
    groups,
    vectors,
    *,
    representative_limit=REPRESENTATIVE_LIMIT,
    threshold=MIN_SCORE,
):
    assessment = assess_story(
        article,
        groups,
        vectors,
        representative_limit=representative_limit,
        threshold=threshold,
    )
    if assessment["reason"] == "accepted":
        return assessment["scores"][0][1]
    return None


def ranked_representatives(members, vectors):
    # Count identical coverage once. The sum of unit vectors gives the same
    # ranking as average pairwise cosine, without building a pairwise matrix.
    total = Counter()
    seen = set()
    for member in members:
        vector = vectors[member.id]
        signature = frozenset(vector.items())
        if signature not in seen:
            total.update(vector)
            seen.add(signature)

    def rank(member):
        centrality = sum(
            weight * total[term] for term, weight in vectors[member.id].items()
        )
        return (
            -round(centrality, 10),
            not bool((member.content or "").strip()),
            article_time(member),
            member.id,
        )

    return sorted(members, key=rank)


def representative(members, vectors):
    return ranked_representatives(members, vectors)[0]
