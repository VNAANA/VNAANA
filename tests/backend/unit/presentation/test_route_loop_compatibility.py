"""Route checks must work when other test tooling already owns an event loop."""

import pytest

from tests.backend.unit.presentation import test_ai_routes, test_tag_routes


@pytest.mark.asyncio
async def test_route_checks_with_an_existing_event_loop():
    # Calling these synchronous checks here reproduces the nested-loop condition.
    test_tag_routes.test_list_tags_returns_ids_and_names_without_authentication()
    test_ai_routes.test_unsupported_question_returns_http_200_with_insufficient_information()
