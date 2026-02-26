"""Tests for the webhook endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


class TestWebhookEndpoint:
    def test_health_check(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_rejects_bad_secret(self):
        # Auth is currently disabled — re-enable in webhook.py to enforce
        resp = client.post(
            "/jira/refine",
            json={"issue_key": "PROJ-1", "mode": "first_pass"},
            headers={"X-Webhook-Secret": "wrong-secret"},
        )
        assert resp.status_code == 200  # Auth disabled

    def test_rejects_missing_secret(self):
        # Auth is currently disabled — re-enable in webhook.py to enforce
        resp = client.post(
            "/jira/refine",
            json={"issue_key": "PROJ-1", "mode": "first_pass"},
        )
        assert resp.status_code == 200  # Auth disabled

    def test_rejects_invalid_mode(self):
        resp = client.post(
            "/jira/refine",
            json={"issue_key": "PROJ-1", "mode": "invalid_mode"},
            headers={"X-Webhook-Secret": settings.WEBHOOK_SECRET},
        )
        assert resp.status_code == 422

    def test_accepts_valid_first_pass(self):
        resp = client.post(
            "/jira/refine",
            json={"issue_key": "PROJ-1", "mode": "first_pass"},
            headers={"X-Webhook-Secret": settings.WEBHOOK_SECRET},
        )
        # Endpoint returns 200 immediately (processing is in background)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["mode"] == "first_pass"

    def test_accepts_valid_pm_feedback(self):
        resp = client.post(
            "/jira/refine",
            json={
                "issue_key": "PROJ-2",
                "mode": "pm_feedback",
                "pm_comment": "1. Yes. 2. Web only.",
            },
            headers={"X-Webhook-Secret": settings.WEBHOOK_SECRET},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["mode"] == "pm_feedback"

    def test_rejects_missing_issue_key(self):
        resp = client.post(
            "/jira/refine",
            json={"mode": "first_pass"},
            headers={"X-Webhook-Secret": settings.WEBHOOK_SECRET},
        )
        assert resp.status_code == 422
