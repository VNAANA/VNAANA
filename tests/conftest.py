"""Settings for every test in the repository."""

import os

import pytest


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    # Locally a test may skip when something it needs isn't running (local
    # Supabase, npm). CI sets REQUIRE_ALL_TESTS=1 so a skip there fails the run.
    # A @pytest.mark.skip on the test itself is a choice someone made on
    # purpose (with a reason), not something missing, so that one stays a skip.
    deliberate = item.get_closest_marker("skip") is not None
    if report.skipped and not deliberate and os.environ.get("REQUIRE_ALL_TESTS") == "1":
        reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else report.longrepr
        reason = str(reason).removeprefix("Skipped: ")
        report.outcome = "failed"
        report.longrepr = f"Skipped, but REQUIRE_ALL_TESTS=1: {reason}"
    return report
