import json
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings
from review.templates import SYSTEM_PROMPT, USER_TEMPLATE


class ReviewGenerator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None

    async def generate(
        self,
        title: str,
        files: list[str],
        ast: list[dict[str, Any]],
        semgrep: list[dict[str, Any]],
        patches: dict[str, str],
        changed_lines: dict[str, set[int]],
        existing_comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.client:
            return self._fallback(semgrep)
        prompt = USER_TEMPLATE.format(
            title=title,
            files=files,
            ast=ast,
            semgrep=semgrep,
            changed_lines={path: sorted(lines) for path, lines in changed_lines.items()},
            patches=patches,
            existing_comments=[
                {"path": c.get("path"), "line": c.get("line"), "body": c.get("body", "")[:500]} for c in existing_comments[:100]
            ],
        )
        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            return json.loads(response.choices[0].message.content or "{}")
        except Exception as exc:
            return {
                "summary": f"OpenAI review generation failed; Semgrep-only fallback used. Error type: {type(exc).__name__}",
                "findings": self._fallback(semgrep)["findings"],
            }

    def _fallback(self, semgrep: list[dict[str, Any]]) -> dict[str, Any]:
        findings = [
            {
                "path": item["path"],
                "line": item["line"],
                "severity": item.get("severity", "INFO"),
                "title": "Semgrep finding",
                "body": f"Semgrep reported: {item.get('message', 'security issue')}",
                "evidence": item.get("message", "semgrep"),
                "explanation": "This finding comes directly from Semgrep security analysis of the changed file.",
                "confidence": "HIGH",
            }
            for item in semgrep
            if item.get("path")
        ]
        return {"summary": "Automated review completed using Semgrep evidence.", "findings": findings}
