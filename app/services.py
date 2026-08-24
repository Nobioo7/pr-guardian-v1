from typing import Any

from app.config import get_settings
from github.client import GitHubClient
from github.comment import to_review_comment
from github.events import pr_context
from parser.tree_sitter import ast_summary
from review.generator import ReviewGenerator
from scanner.semgrep import run_semgrep


class ReviewService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.github = GitHubClient()
        self.generator = ReviewGenerator()

    async def review_pull_request(self, payload: dict[str, Any]) -> None:
        ctx = pr_context(payload)
        pr_files = await self.github.list_pr_files(ctx["installation_id"], ctx["owner"], ctx["repo"], ctx["number"])
        selected = [f for f in pr_files if f.get("status") != "removed"][: self.settings.max_files_per_review]
        contents: dict[str, str] = {}
        patches: dict[str, str] = {}
        for file in selected:
            path = file["filename"]
            patches[path] = (file.get("patch") or "")[: self.settings.max_patch_chars]
            try:
                contents[path] = await self.github.get_file(ctx["installation_id"], ctx["owner"], ctx["repo"], path, ctx["head_sha"])
            except Exception:
                contents[path] = patches[path]
        ast = [ast_summary(path, source) for path, source in contents.items()]
        semgrep = run_semgrep(contents)
        review = await self.generator.generate(ctx["title"], list(contents), ast, semgrep, patches)
        comments = [comment for finding in review.get("findings", []) if (comment := to_review_comment(finding))]
        if self.settings.post_review_comments:
            await self.github.create_review(ctx["installation_id"], ctx["owner"], ctx["repo"], ctx["number"], review.get("summary", "PR Guardian review completed."), comments[:30])
