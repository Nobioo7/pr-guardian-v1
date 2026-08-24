import hashlib
import hmac

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_webhook_rejects_invalid_signature(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    response = TestClient(app).post("/webhooks/github", json={}, headers={"X-Hub-Signature-256": "sha256=bad"})
    assert response.status_code == 401


def test_webhook_accepts_ignored_signed_event(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    body = b'{"zen":"Keep it logically awesome."}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    response = TestClient(app).post("/webhooks/github", content=body, headers={"X-Hub-Signature-256": sig, "X-GitHub-Event": "ping"})
    assert response.status_code == 202
    assert response.json() == {"status": "ignored"}
