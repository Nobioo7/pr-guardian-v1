from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.services import ReviewService
from github.webhook import verify_signature

router = APIRouter()


@router.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
) -> dict[str, str]:
    body = await request.body()
    if not verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature")
    payload = await request.json()
    if x_github_event == "pull_request" and payload.get("action") in {"opened", "synchronize", "reopened", "ready_for_review"}:
        background_tasks.add_task(ReviewService().review_pull_request, payload)
        return {"status": "queued"}
    return {"status": "ignored"}
