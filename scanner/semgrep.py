import json
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


def _safe_relative_path(path: str) -> Path | None:
    posix = PurePosixPath(path)
    if posix.is_absolute() or not path or ".." in posix.parts:
        return None
    return Path(*posix.parts)


def dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int, str]] = set()
    unique: list[dict[str, Any]] = []
    for finding in findings:
        key = (str(finding.get("path", "")), int(finding.get("line", 0)), str(finding.get("check_id") or finding.get("message", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def filter_to_changed_lines(findings: list[dict[str, Any]], changed_lines: dict[str, set[int]] | None) -> list[dict[str, Any]]:
    if changed_lines is None:
        return findings
    return [finding for finding in findings if int(finding.get("line", 0)) in changed_lines.get(str(finding.get("path", "")), set())]


def _warning(message: str) -> list[dict[str, Any]]:
    return [{"path": "", "line": 1, "severity": "WARNING", "message": message[:1000]}]


def run_semgrep(files: dict[str, str], changed_lines: dict[str, set[int]] | None = None) -> list[dict[str, Any]]:
    if not files:
        return []
    if not shutil.which("semgrep"):
        return _warning("semgrep executable is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path_map: dict[Path, str] = {}
        for path, content in files.items():
            safe = _safe_relative_path(path)
            if safe is None:
                continue
            target = root / safe
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            path_map[target.resolve()] = path
        cmd = ["semgrep", "--config", "p/security-audit", "--json", "--quiet", str(root)]
        try:
            completed = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=120)
            if completed.returncode not in {0, 1}:
                return _warning(completed.stderr.strip() or "semgrep failed")
            data = json.loads(completed.stdout or "{}")
        except subprocess.TimeoutExpired:
            return _warning("semgrep timed out")
        except (OSError, json.JSONDecodeError) as exc:
            return _warning(f"semgrep failed: {type(exc).__name__}")
        findings = []
        for result in data.get("results", []):
            result_path = Path(result["path"]).resolve()
            original_path = path_map.get(result_path, str(result_path.relative_to(root)))
            extra = result.get("extra", {})
            findings.append(
                {
                    "path": original_path,
                    "line": result["start"]["line"],
                    "end_line": result["end"]["line"],
                    "severity": extra.get("severity", "INFO"),
                    "message": extra.get("message", result.get("check_id", "semgrep finding")),
                    "check_id": result.get("check_id", ""),
                    "metadata": extra.get("metadata", {}),
                    "lines": extra.get("lines", ""),
                }
            )
        return filter_to_changed_lines(dedupe_findings(findings), changed_lines)
