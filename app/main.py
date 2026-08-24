from fastapi import FastAPI
from app.routes import router
from app.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
