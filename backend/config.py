from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/reader_agent"

    # FIPAI
    fipai_base_url: str = "http://127.0.0.1:8000"
    fipai_instance_id: str = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    fipai_bearer_token: str = ""
    fipai_api_key: str = ""
    fipai_timeout_sec: int = 120

    # Storage
    storage_url: str = "./storage"

    # OpenAI (for embeddings)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.deepseek.com/v1"
    openai_model: str = "text-embedding-3-small"

    # 直接 LLM（AI 导读等生成；后续可替换为 FIPAI 接入）
    llm_chat_model: str = "deepseek-chat"

    # App
    app_name: str = "Reader Agent Backend"
    debug: bool = False
    rag_min_citations: int = 2
    auth_secret_key: str = "dev-only-secret-do-not-use-in-production"
    auth_token_ttl_hours: int = 24
    dev_login_users: str = '{"demo@example.com":"demo"}'
    cors_origins: str = "http://localhost:3001,http://127.0.0.1:3001"
    public_storage_enabled: bool = True
    auto_generate_note: bool = True

    def cors_origin_list(self) -> List[str]:
        origins = [x.strip() for x in (self.cors_origins or "").split(",") if x.strip()]
        return origins or ["http://localhost:3001"]

    def validate_security_config(self) -> None:
        """Validate security-related configuration. Call at startup."""
        import warnings
        import os
        if self.auth_secret_key == "dev-only-secret-do-not-use-in-production":
            if os.getenv("AUTH_SECRET_KEY"):
                warnings.warn(
                    "AUTH_SECRET_KEY is set but not being used. "
                    "Check your environment variable name.",
                    UserWarning,
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    "SECURITY WARNING: auth_secret_key is using default value. "
                    "Set AUTH_SECRET_KEY environment variable in production.",
                    UserWarning,
                    stacklevel=2,
                )
        if not self.openai_api_key:
            warnings.warn(
                "RAG WARNING: openai_api_key not configured. RAG will use "
                "hash-based fake embeddings which produce incorrect similarity scores.",
                UserWarning,
                stacklevel=2,
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
