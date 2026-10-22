from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://proofflow:proofflow@localhost:5433/proofflow"
    test_database_url: str | None = None
    packet_path: str = "../reference/okafor_lindqvist_2025_packet.json"
    cors_origins: str = "http://localhost:3000"
    demo_identity_enabled: bool = True
    default_demo_user: str = "st-01"

    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 30.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_provider and self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
