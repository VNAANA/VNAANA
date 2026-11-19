"""Topic choices on the profile page are saved to the backend."""

from playwright.sync_api import Page, expect


def saved(response) -> bool:
    return response.request.method == "PUT" and response.url.endswith("/preferences") and response.ok


def test_topic_choices_survive_a_reload(logged_in_page: Page):
    page = logged_in_page
    page.goto("/#profile?tab=topics")

    liked = page.get_by_role("group", name="Liked topics", exact=True)
    disliked = page.get_by_role("group", name="Disliked topics", exact=True)
    with page.expect_response(saved):
        liked.get_by_text("Technology", exact=True).click()
    with page.expect_response(saved):
        disliked.get_by_text("Sports", exact=True).click()

    # After a reload the page only knows what the backend sent back.
    page.reload()
    liked = page.get_by_role("group", name="Liked topics", exact=True)
    disliked = page.get_by_role("group", name="Disliked topics", exact=True)
    expect(liked.get_by_role("checkbox", name="Technology")).to_be_checked()
    expect(disliked.get_by_role("checkbox", name="Sports")).to_be_checked()
    expect(liked.get_by_role("checkbox", name="Science")).not_to_be_checked()
