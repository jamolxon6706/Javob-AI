from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://javobai:secret@localhost:5432/javobai"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "change_me"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 30
    otp_ttl_seconds: int = 300

    # Auth cookies (Phase 6 — httpOnly transport to the dashboard).
    # COOKIE_SECURE=false in local dev (HTTP), true in prod.
    cookie_secure: bool = False
    # Empty in dev; ".javobai.uz" in prod so the cookie crosses app./api. subdomains.
    cookie_domain: str = ""
    cookie_samesite: str = "lax"

    # Encryption
    fernet_key: str = "change_me"

    # AI / LLM (Phase 8 — operator copilot). Mirrors apps/worker's WorkerSettings
    # so both processes read the same env vars without sharing a package.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_timeout_seconds: float = 15.0

    # Phase 8 — one-time websocket auth ticket TTL (seconds).
    ws_ticket_ttl_seconds: int = 60


    # WhatsApp Cloud API (Phase 9)
    whatsapp_verify_token: str = "javobai_wa_verify"
    whatsapp_app_secret: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""

    # Meta (Instagram + Facebook) (Phase 10)
    meta_verify_token: str = "javobai_meta_verify"
    meta_app_secret: str = ""

    # Agentic (Phase 11)
    action_timeout_seconds: float = 10.0

    # App
    environment: str = "development"
    api_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
