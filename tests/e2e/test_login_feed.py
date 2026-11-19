"""An existing user logs in and sees the news feed."""

from playwright.sync_api import Page, expect

from tests.e2e.support import ARTICLE_TITLES, log_in


def test_login_shows_the_seeded_articles(page: Page, ready_user):
    log_in(page, ready_user["email"], ready_user["password"])

    feed = page.get_by_role("main", name="For You feed")
    for title in ARTICLE_TITLES:
        expect(feed.get_by_role("article", name=title)).to_have_count(1)
    # Consent and onboarding are done for this account, so no pop-up blocks the feed.
    expect(page.get_by_role("dialog")).to_have_count(0)
