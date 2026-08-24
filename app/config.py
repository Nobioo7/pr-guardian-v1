from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PR Guardian V1"
    github_app_id: str = ""
    github_private_key: str = ""
    github_webhook_secret: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    max_files_per_review: int = 20
    max_patch_chars: int = 12000
    post_review_comments: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PR_GUARDIAN_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
