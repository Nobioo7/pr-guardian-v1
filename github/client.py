import asyncio
import base64
import time
from typing import Any
from urllib.parse import quote

import httpx
import jwt

from app.config import get_settings


class GitHubClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = "https://api.github.com"
        self._tokens: dict[int, tuple[str, float]] = {}

    def _app_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 540, "iss": self.settings.github_app_id}
        return jwt.encode(payload, self.settings.github_private_key.replace("\\n", "\n"), algorithm="RS256")

    async def _installation_token(self, installation_id: int) -> str:
        cached = self._tokens.get(installation_id)
        now = time.time()
        if cached and cached[1] > now + 60:
            return cached[0]
        headers = {
            "Authorization": f"Bearer {self._app_jwt()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=30) as client:
            response = await self._send_with_retries(client, "POST", f"/app/installations/{installation_id}/access_tokens")
            data = response.json()
            expires_at = data.get("expires_at", "")
            # GitHub returns ISO-8601 UTC. Fall back to the documented one-hour token lifetime if parsing fails.
            try:
                import datetime as dt

                expires = dt.datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                expires = now + 3540
            self._tokens[installation_id] = (data["token"], expires)
            return data["token"]

    async def _send_with_retries(self, client: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.settings.github_max_retries):
            try:
                response = await client.request(method, url, **kwargs)
                if response.status_code not in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                    return response
                response.raise_for_status()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                if attempt == self.settings.github_max_retries - 1:
                    break
                await asyncio.sleep(0.5 * (2**attempt))
        if last_error:
            raise last_error
        raise RuntimeError("GitHub request failed without a response")

    async def request(self, installation_id: int, method: str, url: str, **kwargs: Any) -> Any:
        token = await self._installation_token(installation_id)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        async with httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=60) as client:
            response = await self._send_with_retries(client, method, url, **kwargs)
            return response.json() if response.content else None

    async def list_pr_files(self, installation_id: int, owner: str, repo: str, pull_number: int) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        page = 1
        while len(files) < self.settings.max_files_per_review:
            data = await self.request(
                installation_id,
                "GET",
                f"/repos/{owner}/{repo}/pulls/{pull_number}/files",
                params={"per_page": 100, "page": page},
            )
            if not data:
                break
            files.extend(data)
            if len(data) < 100:
                break
            page += 1
        return files[: self.settings.max_files_per_review]

    async def get_pull_request(self, installation_id: int, owner: str, repo: str, pull_number: int) -> dict[str, Any]:
        return await self.request(installation_id, "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}")

    async def list_existing_review_comments(self, installation_id: int, owner: str, repo: str, pull_number: int) -> list[dict[str, Any]]:
        return await self.request(installation_id, "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}/comments")

    async def get_file(self, installation_id: int, owner: str, repo: str, path: str, ref: str) -> str:
        encoded_path = quote(path, safe="/")
        data = await self.request(installation_id, "GET", f"/repos/{owner}/{repo}/contents/{encoded_path}", params={"ref": ref})
        if data.get("type") != "file" or data.get("encoding") != "base64":
            raise ValueError("unsupported GitHub content response")
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")

    async def create_review(
        self, installation_id: int, owner: str, repo: str, pull_number: int, body: str, comments: list[dict[str, Any]]
    ) -> Any:
        payload = {"event": "COMMENT", "body": body, "comments": comments}
        return await self.request(installation_id, "POST", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews", json=payload)
