
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "tests" / "performance" / "data" / "auth-state.json"

API_URL = os.environ.get("PERFORMANCE_SUPABASE_URL")
PUBLISHABLE_KEY = os.environ.get("PERFORMANCE_SUPABASE_PUBLISHABLE_KEY")

EMAIL = "performance@vnaana.test"
PASSWORD = "Vnaana-Performance-Test-2026!"
FRONTEND_ORIGIN = "http://localhost:5173"

if not API_URL or not PUBLISHABLE_KEY:
    raise RuntimeError("Performance Supabase environment variables are missing.")

response = httpx.post(
    f"{API_URL}/auth/v1/token",
    params={"grant_type": "password"},
    headers={"apikey": PUBLISHABLE_KEY},
    json={"email": EMAIL, "password": PASSWORD},
    timeout=30,
)
response.raise_for_status()

session = response.json()

# Supabase JS derives the local storage key from the first hostname segment.
project_ref = urlparse(API_URL).hostname.split(".")[0]
storage_key = f"sb-{urlparse(API_URL).hostname.split('.')[0]}-auth-token"

storage_state = {
    "cookies": [],
    "origins": [
        {
            "origin": FRONTEND_ORIGIN,
            "localStorage": [
                {
                    "name": storage_key,
                    "value": json.dumps(session),
                }
            ],
        }
    ],
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(storage_state, indent=2), encoding="utf-8")

print(f"Authenticated browser state saved: {OUTPUT}")
print(f"Storage key: {storage_key}")
