"""Read-only API load profile for VNAANA.

Run only against a local test instance or an explicitly approved staging URL.
The tasks below are based on endpoints already visible in the supplied E2E
fixtures: GET /tags and GET /articles/random?limit=5.
"""
import os
from locust import HttpUser, between, task


class VnaanaApiUser(HttpUser):
    wait_time = between(2, 5)

    def on_start(self):
        token = os.getenv("LOAD_TEST_BEARER_TOKEN")
        if token:
            self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(3)
    def load_feed(self):
        with self.client.get(
            "/articles/random?limit=5",
            name="/articles/random?limit=5",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Feed returned HTTP {response.status_code}")
                return
            try:
                payload = response.json()
            except ValueError:
                response.failure("Feed response was not valid JSON")
                return
            if not isinstance(payload, list):
                response.failure("Expected the feed response to be a JSON list")
            elif len(payload) > 5:
                response.failure(f"Expected at most 5 articles, got {len(payload)}")

    @task(1)
    def load_tags(self):
        # The E2E fixture confirms this endpoint exists; its response schema
        # is intentionally not assumed here.
        with self.client.get("/tags", name="/tags", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Tags returned HTTP {response.status_code}")
