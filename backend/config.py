"""
LexJal — Configuración central
Carga variables de entorno y expone settings tipados.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    claude_model: str = Field("claude-sonnet-4-20250514", env="CLAUDE_MODEL")

    # PostgreSQL
    database_url: str = Field(..., env="DATABASE_URL")

    # Redis
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")

    # ChromaDB
    chroma_host: str = Field("localhost", env="CHROMA_HOST")
    chroma_port: int = Field(8000, env="CHROMA_PORT")
    chroma_collection: str = Field("leyes_jalisco", env="CHROMA_COLLECTION")

    # JWT
    secret_key: str = Field(..., env="SECRET_KEY")
    access_token_expire_minutes: int = Field(1440, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # App
    environment: str = Field("development", env="ENVIRONMENT")
    cors_origins: list[str] = Field(["*"], env="CORS_ORIGINS")

    # Reglas de negocio
    free_daily_limit: int = Field(1, env="FREE_DAILY_LIMIT")

    # Stripe (fase 3)
    stripe_secret_key: str = Field("", env="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field("", env="STRIPE_WEBHOOK_SECRET")

    # Meta / WhatsApp (fase 2)
    meta_verify_token: str = Field("", env="META_VERIFY_TOKEN")
    whatsapp_phone_number_id: str = Field("", env="WHATSAPP_PHONE_NUMBER_ID")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
