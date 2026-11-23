"""A new visitor creates an account with email and password."""

from uuid import uuid4

from playwright.sync_api import Page, expect

from tests.e2e.support import SEEDED_ARTICLE

PASSWORD = "new-user-password-123"


def test_new_account_lands_in_the_app(page: Page):
    # A unique address every run, so this test never depends on an earlier one.
    email = f"e2e+{uuid4().hex[:8]}@vnaana.test"

    page.goto("/#sign-up")
    page.get_by_label("First name").fill("Test")
    page.get_by_label("Last name").fill("User")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_label("Repeat password").fill(PASSWORD)
    page.get_by_text("I agree that Virtual News Anchor").click()
    page.get_by_role("button", name="Create account", exact=True).click()

    # Consent was given in the form, so a new account goes straight to the topic pop-up.
    topics = page.get_by_role("dialog", name="What news do you want?")
    expect(topics).to_be_visible()
    topics.get_by_role("button", name="Skip for now").click()

    expect(topics).to_be_hidden()
    expect(page.get_by_role("article", name=SEEDED_ARTICLE)).to_have_count(5)
