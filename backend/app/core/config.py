from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TruthLens AI API"
    environment: str = "development"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_provider: Literal["sqlite", "supabase"] = "supabase"
    sqlite_database_path: str = "data/truthlens.db"
    model_provider: Literal["traditional", "transformer"] = "traditional"
    transformer_model_path: str = "backend/models/liar_distilbert"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    google_fact_check_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


settings = Settings()
