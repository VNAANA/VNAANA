"""Shared values and steps for the end-to-end tests."""

import re

from playwright.sync_api import Page

# Backend/main.py only allows this origin (CORS), so Vite has to run exactly here.
FRONTEND_URL = "http://localhost:5173"
API_PORT = 8765
API_URL = f"http://127.0.0.1:{API_PORT}"

TEST_EMAIL = "e2e@vnaana.test"
TEST_PASSWORD = "e2e-password-123"

# The feed asks for 5 random articles, so seeding exactly 5 means all of them show up.
ARTICLE_TITLES = [f"E2E article {number}" for number in range(1, 6)]
SEEDED_ARTICLE = re.compile(r"^E2E article \d$")


def log_in(page: Page, email: str, password: str) -> None:
    page.goto("/#login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Log in", exact=True).click()
