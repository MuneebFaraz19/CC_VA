"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "sqlite:///./patients.db"

    # LLM (Groq)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Vapi
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""
    vapi_webhook_secret: str = ""
    public_base_url: str = "http://localhost:8000"

    # Server
    port: int = 8000
    log_level: str = "info"

    @property
    def vapi_configured(self) -> bool:
        return bool(self.vapi_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
