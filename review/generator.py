import json
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings
from review.templates import SYSTEM_PROMPT, USER_TEMPLATE


class ReviewGenerator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None

    async def generate(self, title: str, files: list[str], ast: list[dict[str, Any]], semgrep: list[dict[str, Any]], patches: dict[str, str]) -> dict[str, Any]:
        if not self.client:
            return self._fallback(semgrep)
        prompt = USER_TEMPLATE.format(title=title, files=files, ast=ast, semgrep=semgrep, patches=patches)
        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(response.choices[0].message.content or "{}")

    def _fallback(self, semgrep: list[dict[str, Any]]) -> dict[str, Any]:
        findings = [{
            "path": item["path"],
            "line": item["line"],
            "severity": item.get("severity", "INFO"),
            "title": "Semgrep finding",
            "body": f"Semgrep reported: {item.get('message', 'security issue')}",
            "evidence": item.get("message", "semgrep"),
        } for item in semgrep if item.get("path")]
        return {"summary": "Automated review completed using Semgrep evidence.", "findings": findings}
