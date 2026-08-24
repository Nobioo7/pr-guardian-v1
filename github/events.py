from typing import Any


def pr_context(payload: dict[str, Any]) -> dict[str, Any]:
    repo = payload["repository"]
    pr = payload["pull_request"]
    return {
        "installation_id": payload["installation"]["id"],
        "owner": repo["owner"]["login"],
        "repo": repo["name"],
        "number": pr["number"],
        "head_sha": pr["head"]["sha"],
        "title": pr.get("title", ""),
    }
