import hashlib
import hmac

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import ReviewService
from github.comment import to_review_comment
from github.webhook import verify_signature
from review.evidence import changed_lines_from_patch, normalize_findings
from scanner.semgrep import run_semgrep


def signed_headers(secret: str, body: bytes, event: str = "ping", delivery: str = "delivery-1") -> dict[str, str]:
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": sig, "X-GitHub-Event": event, "X-GitHub-Delivery": delivery}


def test_verify_signature_accepts_valid_signature(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    body = b'{"ok":true}'
    assert verify_signature(body, signed_headers("secret", body)["X-Hub-Signature-256"])


def test_webhook_rejects_invalid_signature(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    response = TestClient(app).post("/webhook", json={}, headers={"X-Hub-Signature-256": "sha256=bad"})
    assert response.status_code == 401


def test_webhook_rejects_signed_invalid_json(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    body = b"{not-json"
    response = TestClient(app).post("/webhook", content=body, headers=signed_headers("secret", body))
    assert response.status_code == 400


def test_webhook_accepts_ignored_signed_event(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    body = b'{"zen":"Keep it logically awesome."}'
    response = TestClient(app).post("/webhook", content=body, headers=signed_headers("secret", body))
    assert response.status_code == 202
    assert response.json() == {"status": "ignored"}


def test_webhook_queues_supported_pull_request(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("PR_GUARDIAN_STATE_DB_PATH", str(tmp_path / "state.sqlite3"))
    monkeypatch.setattr(ReviewService, "review_pull_request", lambda self, payload, delivery_id=None: None)
    body = (
        b'{"action":"opened","installation":{"id":1},"repository":{"owner":{"login":"octo"},"name":"repo"},'
        b'"pull_request":{"number":7,"draft":false,"head":{"sha":"abc"}}}'
    )
    response = TestClient(app).post("/webhook", content=body, headers=signed_headers("secret", body, "pull_request", "delivery-pr"))
    assert response.status_code == 202
    assert response.json() == {"status": "queued"}


def test_webhook_deduplicates_delivery(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("PR_GUARDIAN_GITHUB_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("PR_GUARDIAN_STATE_DB_PATH", str(tmp_path / "state.sqlite3"))
    monkeypatch.setattr(ReviewService, "review_pull_request", lambda self, payload, delivery_id=None: None)
    body = (
        b'{"action":"opened","installation":{"id":1},"repository":{"owner":{"login":"octo"},"name":"repo"},'
        b'"pull_request":{"number":7,"draft":false,"head":{"sha":"abc"}}}'
    )
    headers = signed_headers("secret", body, "pull_request", "same-delivery")
    client = TestClient(app)
    assert client.post("/webhook", content=body, headers=headers).json() == {"status": "queued"}
    assert client.post("/webhook", content=body, headers=headers).json() == {"status": "duplicate"}


def test_health_aliases_work():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/healthz").json() == {"status": "ok"}


def test_changed_lines_and_comment_filtering():
    patch = "@@ -1,2 +1,3 @@\n a\n+b\n c\n"
    changed = {"app.py": changed_lines_from_patch(patch)}
    assert changed == {"app.py": {2}}
    assert to_review_comment({"path": "app.py", "line": 2, "body": "ok"}, changed) is not None
    assert to_review_comment({"path": "app.py", "line": 1, "body": "skip"}, changed) is None


def test_normalize_findings_requires_evidence_confidence_and_changed_line():
    patches = {"app.py": "@@ -1,2 +1,3 @@\n a\n+b\n c\n"}
    review = {
        "summary": "done",
        "findings": [
            {"path": "app.py", "line": 2, "title": "Real", "evidence": "added b", "explanation": "bad", "confidence": "HIGH"},
            {"path": "app.py", "line": 1, "title": "Unchanged", "evidence": "x", "explanation": "bad", "confidence": "HIGH"},
            {"path": "app.py", "line": 2, "title": "Real", "evidence": "added b", "explanation": "duplicate", "confidence": "HIGH"},
        ],
    }
    normalized = normalize_findings(review, patches, [], [])
    assert len(normalized["findings"]) == 1
    assert normalized["findings"][0]["confidence"] == "HIGH"


def test_semgrep_missing_binary_is_non_fatal(monkeypatch):
    monkeypatch.setenv("PATH", "")
    findings = run_semgrep({"app.py": "print('hello')"})
    assert findings[0]["severity"] == "WARNING"
    assert "not installed" in findings[0]["message"]
