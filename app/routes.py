from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.services import ReviewService
from github.webhook import verify_signature

router = APIRouter()
SUPPORTED_PR_ACTIONS = {"opened", "synchronize", "reopened"}


@router.get("/health")
@router.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
@router.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
) -> dict[str, str]:
    body = await request.body()
    if not verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature")
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid JSON payload") from exc
    if x_github_event == "pull_request" and payload.get("action") in SUPPORTED_PR_ACTIONS:
        if payload.get("pull_request", {}).get("draft"):
            return {"status": "ignored_draft"}
        claimed = ReviewService().queue_review(background_tasks, payload, x_github_delivery or None)
        return {"status": "queued" if claimed else "duplicate"}
    return {"status": "ignored"}
