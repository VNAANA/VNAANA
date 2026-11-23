"""Route checks must work when other test tooling already owns an event loop."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from tests.backend.unit.presentation import (
    test_ai_routes,
    test_story_translation_route,
    test_tag_routes,
)


async def run_checks_inside_a_running_loop():
    # These are synchronous checks; calling them while this loop is running
    # reproduces the nested-loop condition.
    test_tag_routes.test_list_tags_returns_ids_and_names_without_authentication()
    test_ai_routes.test_unsupported_question_returns_http_200_with_insufficient_information()
    test_story_translation_route.test_no_token_means_anonymous_without_calling_supabase()


def test_route_checks_with_an_existing_event_loop():
    # Not an async test on purpose: after the E2E tests Playwright keeps its own
    # loop running in this thread, so pytest-asyncio can't start one here. A new
    # thread never has a running loop, so the condition is the same in every run.
    with ThreadPoolExecutor(max_workers=1) as pool:
        # result() re-raises a failed assert from the thread.
        pool.submit(asyncio.run, run_checks_inside_a_running_loop()).result()
