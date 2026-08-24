import hashlib
import hmac

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from github.webhook import verify_signature
from scanner.semgrep import run_semgrep


def signed_headers(secret: str, body: bytes, event: str = "ping") -> dict[str, str]:
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": sig, "X-GitHub-Event": event}


def test_verify_signature_accepts_valid_signature(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    body = b'{"ok":true}'
    assert verify_signature(body, signed_headers("secret", body)["X-Hub-Signature-256"])


def test_webhook_rejects_invalid_signature(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    response = TestClient(app).post("/webhooks/github", json={}, headers={"X-Hub-Signature-256": "sha256=bad"})
    assert response.status_code == 401


def test_webhook_accepts_ignored_signed_event(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    body = b'{"zen":"Keep it logically awesome."}'
    response = TestClient(app).post("/webhooks/github", content=body, headers=signed_headers("secret", body))
    assert response.status_code == 202
    assert response.json() == {"status": "ignored"}


def test_semgrep_missing_binary_is_non_fatal(monkeypatch):
    monkeypatch.setenv("PATH", "")
    findings = run_semgrep({"app.py": "print('hello')"})
    assert findings[0]["severity"] == "WARNING"
    assert "not installed" in findings[0]["message"]
