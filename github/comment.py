from typing import Any


def to_review_comment(finding: dict[str, Any], changed_lines: dict[str, set[int]] | None = None) -> dict[str, Any] | None:
    path = finding.get("path")
    line = finding.get("line")
    body = finding.get("body")
    if not path or not line or not body:
        return None
    line_number = int(line)
    if changed_lines is not None and line_number not in changed_lines.get(path, set()):
        return None
    return {"path": path, "line": line_number, "side": "RIGHT", "body": body}
