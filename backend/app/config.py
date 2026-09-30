"""DataPilot AI configuration via environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "DataPilot AI"
    api_prefix: str = "/api/v1"
    debug: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    # --- Database (SQLite default; PostgreSQL via env) ---
    database_url: str = "sqlite:///./datapilot.db"

    # --- LLM (optional enhancer; system works fully without it) ---
    openai_api_key: str = ""

    # --- Cloudinary (optional until keys provided) ---
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # --- Paths ---
    demo_data_dir: str = "app/seed/demo_data"
    # Where bundled demo assets live (used when Cloudinary keys absent)
    local_asset_dir: str = "app/seed/demo_data"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cloudinary_configured(self) -> bool:
        return bool(
            self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
