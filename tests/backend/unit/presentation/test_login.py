"""Password-login contract tests with mocked Supabase; no network or database."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.Presentation.routers import login


@pytest.fixture
def context(monkeypatch):
    settings = SimpleNamespace(supabase_url="https://auth.example/", supabase_publishable_key="public-test-key")
    monkeypatch.setattr(login, "get_settings", lambda: settings)
    post = AsyncMock(return_value=httpx.Response(200, json={
        "access_token": "test-access-token", "token_type": "bearer", "expires_in": 1234,
        "refresh_token": "private-refresh-token", "user": {"id": "test-user"},
    }))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    app = FastAPI()
    app.include_router(login.router)
    with TestClient(app) as client:
        yield client, post, settings


def test_success_without_prior_token(context):
    client, post, _ = context
    response = client.post('/auth/login', json={'email': ' tester@example.com ', 'password': ' test-secret '})
    assert response.status_code == 200
    assert response.json() == {'access_token': 'test-access-token', 'token_type': 'bearer', 'expires_in': 1234}
    assert response.headers['Cache-Control'] == 'no-store'
    post.assert_awaited_once_with('https://auth.example/auth/v1/token',
        params={'grant_type': 'password'}, headers={'apikey': 'public-test-key'},
        json={'email': 'tester@example.com', 'password': ' test-secret '})


@pytest.mark.parametrize('status, expected', [(400, 401), (401, 401), (403, 401), (422, 401), (429, 429), (500, 503)])
def test_upstream_errors_are_sanitized(context, status, expected):
    client, post, _ = context
    post.return_value = httpx.Response(status, json={'message': 'sensitive-upstream-details'})
    response = client.post('/auth/login', json={'email': 'tester@example.com', 'password': 'test-secret'})
    assert response.status_code == expected
    assert 'sensitive-upstream-details' not in response.text
    assert response.headers['Cache-Control'] == 'no-store'


def test_timeout(context):
    client, post, _ = context
    post.side_effect = httpx.ReadTimeout('sensitive-network-details')
    response = client.post('/auth/login', json={'email': 'tester@example.com', 'password': 'test-secret'})
    assert response.status_code == 503
    assert 'sensitive-network-details' not in response.text


@pytest.mark.parametrize('body', [{}, {'access_token': '', 'token_type': 'bearer', 'expires_in': 10},
                                  {'access_token': 'token', 'token_type': 'bearer', 'expires_in': -1}, []])
def test_invalid_success_response(context, body):
    client, post, _ = context
    post.return_value = httpx.Response(200, json=body)
    assert client.post('/auth/login', json={'email': 'tester@example.com', 'password': 'test-secret'}).status_code == 502


def test_non_json_response(context):
    client, post, _ = context
    post.return_value = httpx.Response(200, text='not-json')
    assert client.post('/auth/login', json={'email': 'tester@example.com', 'password': 'test-secret'}).status_code == 502


def test_unconfigured(context):
    client, post, settings = context
    settings.supabase_url = None
    assert client.post('/auth/login', json={'email': 'tester@example.com', 'password': 'test-secret'}).status_code == 503
    post.assert_not_awaited()


@pytest.mark.parametrize('body', [{'email': 'invalid', 'password': 'test-secret'},
                                  {'email': 'tester@example.com', 'password': {'secret': 'test-secret'}},
                                  {'email': 'tester@example.com', 'password': ''},
                                  {'email': 'tester@example.com', 'extra': 'test-secret'}])
def test_validation_does_not_echo_credentials(context, body):
    client, post, _ = context
    response = client.post('/auth/login', json=body)
    assert response.status_code == 422
    assert 'test-secret' not in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    post.assert_not_awaited()


def test_swagger_password_field_and_public_login(context):
    client, _, _ = context
    schema = client.get('/openapi.json').json()
    assert not schema['paths']['/auth/login']['post'].get('security')
    password = schema['components']['schemas']['PasswordLogin']['properties']['password']
    assert password['format'] == 'password'
    assert password['writeOnly'] is True
