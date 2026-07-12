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

    # Kryptering av tokens i vila m.m. — sätt ett långt slumpvärde i drift!
    secret_key: str = "dev-secret-change-me"

    # Cloudflare API — låter admin hantera Access-vitlistan (testare)
    # direkt från Bodify. Skapa en API-token med behörigheten
    # "Access: Apps and Policies – Edit" i Cloudflare-dashboarden.
    cf_api_token: str = ""
    cf_account_id: str = ""
    cf_access_app_id: str = ""  # Access-applikationens UUID
    cf_access_policy_id: str = ""  # valfri — annars väljs första allow-policyn

    # Publik bas-URL (för OAuth-redirects och webhooks), t.ex.
    # https://bodify.dindomän.se
    public_base_url: str = "http://localhost:3000"

    # Strava (skapa app på https://www.strava.com/settings/api)
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_verify_token: str = "bodify-strava"

    # Withings (skapa app på https://developer.withings.com)
    withings_client_id: str = ""
    withings_client_secret: str = ""

    # Lagring för uppladdade filer (progressfoton) — volym i Docker
    data_dir: str = "./data"

    # AI (Ollama körs lokalt via docker compose --profile ai)
    ollama_url: str = "http://ollama:11434"
    ollama_text_model: str = "llama3.1"
    ollama_vision_model: str = "qwen2.5vl"

    # Web Push (VAPID). Generera nycklar med:
    #   python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); \
    #     print(v.private_pem().decode()); print(v.public_pem().decode())"
    # eller `npx web-push generate-vapid-keys` (base64url-formatet).
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"

    # Endast lokal utveckling: hoppar över Cloudflare-verifieringen helt
    # och agerar som denna e-postadress. Får ALDRIG sättas i produktion.
    dev_auth_email: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
