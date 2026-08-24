import time
from typing import Any

import httpx
import jwt

from app.config import get_settings


class GitHubClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = "https://api.github.com"

    def _app_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 540, "iss": self.settings.github_app_id}
        return jwt.encode(payload, self.settings.github_private_key.replace("\\n", "\n"), algorithm="RS256")

    async def _installation_token(self, installation_id: int) -> str:
        headers = {"Authorization": f"Bearer {self._app_jwt()}", "Accept": "application/vnd.github+json"}
        async with httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=30) as client:
            response = await client.post(f"/app/installations/{installation_id}/access_tokens")
            response.raise_for_status()
            return response.json()["token"]

    async def request(self, installation_id: int, method: str, url: str, **kwargs: Any) -> Any:
        token = await self._installation_token(installation_id)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        async with httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=60) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None

    async def list_pr_files(self, installation_id: int, owner: str, repo: str, pull_number: int) -> list[dict[str, Any]]:
        return await self.request(installation_id, "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}/files")

    async def get_file(self, installation_id: int, owner: str, repo: str, path: str, ref: str) -> str:
        data = await self.request(installation_id, "GET", f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref})
        import base64
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")

    async def create_review(self, installation_id: int, owner: str, repo: str, pull_number: int, body: str, comments: list[dict[str, Any]]) -> Any:
        payload = {"event": "COMMENT", "body": body, "comments": comments}
        return await self.request(installation_id, "POST", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews", json=payload)
