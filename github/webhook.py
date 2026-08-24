import hashlib
import hmac

from app.config import get_settings


def verify_signature(body: bytes, signature_header: str) -> bool:
    secret = get_settings().github_webhook_secret
    if not secret or not signature_header.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature_header)
