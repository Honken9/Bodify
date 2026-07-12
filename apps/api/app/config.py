from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Cloudflare Access
    cf_team_domain: str = ""  # t.ex. "dittteam.cloudflareaccess.com"
    cf_access_aud: str = ""  # Access-applikationens AUD-tag

    # Infrastruktur
    database_url: str = "postgresql+asyncpg://bodify:bodify@localhost:5432/bodify"
    redis_url: str = "redis://localhost:6379/0"

    # Användarhantering
    bootstrap_admin_email: str | None = None  # blir admin vid första inloggningen
    auto_provision_users: bool = False  # skapa konto automatiskt för vitlistade

    # Endast lokal utveckling: hoppar över Cloudflare-verifieringen helt
    # och agerar som denna e-postadress. Får ALDRIG sättas i produktion.
    dev_auth_email: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
