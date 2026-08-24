from typing import Any


def to_review_comment(finding: dict[str, Any]) -> dict[str, Any] | None:
    path = finding.get("path")
    line = finding.get("line")
    body = finding.get("body")
    if not path or not line or not body:
        return None
    return {"path": path, "line": int(line), "side": "RIGHT", "body": body}
