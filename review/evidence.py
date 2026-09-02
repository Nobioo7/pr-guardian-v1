from typing import Any

VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}


def changed_lines_from_patch(patch: str) -> set[int]:
    changed: set[int] = set()
    new_line: int | None = None
    for row in patch.splitlines():
        if row.startswith("@@"):
            marker = " +"
            start = row.find(marker)
            if start == -1:
                new_line = None
                continue
            segment = row[start + len(marker) :].split(" ", 1)[0]
            number = segment.split(",", 1)[0]
            try:
                new_line = int(number)
            except ValueError:
                new_line = None
            continue
        if new_line is None:
            continue
        if row.startswith("+") and not row.startswith("+++"):
            changed.add(new_line)
            new_line += 1
        elif row.startswith("-") and not row.startswith("---"):
            continue
        else:
            new_line += 1
    return changed


def collect_changed_lines(patches: dict[str, str]) -> dict[str, set[int]]:
    return {path: changed_lines_from_patch(patch) for path, patch in patches.items()}


def evidence_by_line(patches: dict[str, str], semgrep: list[dict[str, Any]], ast: list[dict[str, Any]]) -> dict[tuple[str, int], list[str]]:
    evidence: dict[tuple[str, int], list[str]] = {}
    for item in semgrep:
        path = item.get("path")
        line = item.get("line")
        if path and line:
            evidence.setdefault((path, int(line)), []).append(str(item.get("message", "Semgrep finding")))
    for item in ast:
        path = item.get("path")
        for node in item.get("changed_nodes", []):
            line = node.get("start_line")
            if path and line:
                evidence.setdefault((path, int(line)), []).append(f"Changed {node.get('type', 'AST node')} in {path}")
    for path, patch in patches.items():
        for line in changed_lines_from_patch(patch):
            evidence.setdefault((path, line), []).append("Line is part of the pull request diff")
    return evidence


def normalize_findings(
    review: dict[str, Any], patches: dict[str, str], semgrep: list[dict[str, Any]], ast: list[dict[str, Any]]
) -> dict[str, Any]:
    changed_lines = collect_changed_lines(patches)
    evidence = evidence_by_line(patches, semgrep, ast)
    seen: set[tuple[str, int, str]] = set()
    normalized: list[dict[str, Any]] = []
    for finding in review.get("findings", []):
        path = finding.get("path")
        line = finding.get("line")
        if not path or line is None:
            continue
        line_number = int(line)
        if line_number not in changed_lines.get(path, set()):
            continue
        line_evidence = evidence.get((path, line_number), [])
        supplied_evidence = str(finding.get("evidence", "")).strip()
        if not supplied_evidence and not line_evidence:
            continue
        confidence = str(finding.get("confidence", "LOW")).upper()
        if confidence not in VALID_CONFIDENCE:
            confidence = "LOW"
        title = str(finding.get("title", "Review finding")).strip()[:120]
        explanation = str(finding.get("explanation", finding.get("body", ""))).strip()
        evidence_text = supplied_evidence or "; ".join(line_evidence)
        body = f"**{title}**\n\nEvidence: {evidence_text}\n\nExplanation: {explanation}\n\nConfidence: {confidence}"
        key = (path, line_number, title.lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "path": path,
                "line": line_number,
                "severity": finding.get("severity", "INFO"),
                "title": title,
                "body": body,
                "evidence": evidence_text,
                "explanation": explanation,
                "confidence": confidence,
            }
        )
    return {"summary": review.get("summary", "PR Guardian review completed."), "findings": normalized}
