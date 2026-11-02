"""The fake news world the playground runs on.

20 made-up articles over 10 tags. Some articles share tags, so liking one
article also moves others. Articles are published on different days, so
moving the clock forward shows new articles arriving and old ones expiring.

Change anything here freely: titles, tags, days. The rest of the
playground reads this file and adapts.
"""

from dataclasses import dataclass

TAGS: list[str] = [
    "Politics",
    "Sports",
    "Technology",
    "Climate",
    "Economy",
    "Culture",
    "Science",
    "Health",
    "Entertainment",
    "World",
]


@dataclass(frozen=True)
class MockArticle:
    title: str
    summary: str
    tags: tuple[str, ...]
    published_day: int  # day of the simulation the article appears on


ARTICLES: list[MockArticle] = [
    # ---- day 0: what is there when the user starts ----------------------------
    MockArticle(
        "Parliament debates new housing plan",
        "MPs argue over how many homes should be built in the next five years.",
        ("Politics", "Economy"),
        0,
    ),
    MockArticle(
        "Local club wins the national cup final",
        "A last-minute goal decides a final nobody expected them to reach.",
        ("Sports",),
        0,
    ),
    MockArticle(
        "New phone battery lasts a full week",
        "Researchers show a battery cell that charges in minutes and lasts days.",
        ("Technology", "Science"),
        0,
    ),
    MockArticle(
        "Record heat measured across Europe",
        "Several countries break their temperature records in the same week.",
        ("Climate", "World"),
        0,
    ),
    MockArticle(
        "Museum opens free weekends for students",
        "Students get free entry every weekend for the rest of the year.",
        ("Culture",),
        0,
    ),
    MockArticle(
        "Study links sleep to exam results",
        "Students who sleep eight hours score better, a large study finds.",
        ("Science", "Health"),
        0,
    ),
    MockArticle(
        "Streaming service raises its prices",
        "Subscribers will pay more from next month, the company announces.",
        ("Entertainment", "Economy", "Technology"),
        0,
    ),
    MockArticle(
        "Cyclists protest for safer city roads",
        "Thousands ride through the city centre to ask for separate bike lanes.",
        ("Sports", "Politics", "Health"),
        0,
    ),
    # ---- day 3 ------------------------------------------------------------------
    MockArticle(
        "Election polls show a tight race",
        "The two largest parties are only one seat apart in the latest poll.",
        ("Politics",),
        3,
    ),
    MockArticle(
        "Football stadium switches to solar power",
        "The roof of the stadium now produces more energy than a match uses.",
        ("Sports", "Climate", "Technology"),
        3,
    ),
    MockArticle(
        "Festival line-up announced for summer",
        "Organisers reveal the headliners for the country's biggest festival.",
        ("Entertainment", "Culture"),
        3,
    ),
    # ---- day 7 ------------------------------------------------------------------
    MockArticle(
        "Central bank keeps interest rates steady",
        "Rates stay the same for now, but the bank hints at a cut later this year.",
        ("Economy",),
        7,
    ),
    MockArticle(
        "Hospital tests AI to read scans",
        "Doctors try software that flags problems on scans before they look.",
        ("Health", "Technology"),
        7,
    ),
    MockArticle(
        "Floods hit coastal towns abroad",
        "Heavy rain forces thousands of people to leave their homes.",
        ("World", "Climate"),
        7,
    ),
    # ---- day 12 -----------------------------------------------------------------
    MockArticle(
        "Olympic team announced for next games",
        "The national committee names the athletes who will compete.",
        ("Sports", "World"),
        12,
    ),
    MockArticle(
        "Minister resigns after budget dispute",
        "The finance minister steps down after clashing with the cabinet.",
        ("Politics", "Economy"),
        12,
    ),
    MockArticle(
        "Indie game becomes surprise hit",
        "A game made by three students sells a million copies in a week.",
        ("Entertainment", "Technology"),
        12,
    ),
    # ---- day 18 -----------------------------------------------------------------
    MockArticle(
        "New vaccine shows strong trial results",
        "A vaccine against a common virus works in nine out of ten people.",
        ("Health", "Science"),
        18,
    ),
    MockArticle(
        "Climate summit ends without a deal",
        "Countries fail to agree on new targets after two weeks of talks.",
        ("Climate", "Politics", "World"),
        18,
    ),
    MockArticle(
        "Film about local history wins award",
        "A documentary about the city's past wins the main prize at a festival.",
        ("Culture", "Entertainment"),
        18,
    ),
]
