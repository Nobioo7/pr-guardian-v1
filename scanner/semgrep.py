import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def run_semgrep(files: dict[str, str]) -> list[dict[str, Any]]:
    if not files:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for path, content in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        cmd = ["semgrep", "--config", "p/security-audit", "--json", "--quiet", str(root)]
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=120)
        if completed.returncode not in {0, 1}:
            return [{"path": "", "line": 1, "severity": "WARNING", "message": completed.stderr.strip() or "semgrep failed"}]
        data = json.loads(completed.stdout or "{}")
        findings = []
        for result in data.get("results", []):
            findings.append({
                "path": str(Path(result["path"]).relative_to(root)),
                "line": result["start"]["line"],
                "severity": result.get("extra", {}).get("severity", "INFO"),
                "message": result.get("extra", {}).get("message", result.get("check_id", "semgrep finding")),
            })
        return findings
