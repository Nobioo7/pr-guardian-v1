from typing import Any

from fastapi import BackgroundTasks

from app.config import get_settings
from app.state import ReviewState
from github.client import GitHubClient
from github.comment import to_review_comment
from github.events import pr_context
from parser.tree_sitter import ast_summary
from review.evidence import collect_changed_lines, normalize_findings
from review.generator import ReviewGenerator
from scanner.semgrep import run_semgrep


class ReviewService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.github = GitHubClient()
        self.generator = ReviewGenerator()
        self.state = ReviewState()

    def queue_review(self, background_tasks: BackgroundTasks, payload: dict[str, Any], delivery_id: str | None) -> bool:
        if not self.state.claim_delivery(delivery_id):
            return False
        background_tasks.add_task(self.review_pull_request, payload, delivery_id)
        return True

    async def review_pull_request(self, payload: dict[str, Any], delivery_id: str | None = None) -> None:
        ctx = pr_context(payload)
        pull_request = await self.github.get_pull_request(ctx["installation_id"], ctx["owner"], ctx["repo"], ctx["number"])
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
        changed_lines = collect_changed_lines(patches)
        ast = [ast_summary(path, source, changed_lines.get(path, set())) for path, source in contents.items()]
        semgrep = run_semgrep(contents, changed_lines)
        existing_comments = await self.github.list_existing_review_comments(
            ctx["installation_id"], ctx["owner"], ctx["repo"], ctx["number"]
        )
        review = await self.generator.generate(
            pull_request.get("title", ctx["title"]),
            list(contents),
            ast,
            semgrep,
            patches,
            changed_lines,
            existing_comments,
        )
        normalized = normalize_findings(review, patches, semgrep, ast)
        new_findings = self.state.filter_new_findings(ctx["owner"], ctx["repo"], ctx["number"], normalized.get("findings", []))
        comments = [comment for finding in new_findings if (comment := to_review_comment(finding, changed_lines))]
        body = normalized.get("summary", "PR Guardian review completed.")
        if self.settings.post_review_comments:
            await self.github.create_review(ctx["installation_id"], ctx["owner"], ctx["repo"], ctx["number"], body, comments[:30])
        self.state.complete_delivery(delivery_id)
