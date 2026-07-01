from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://javobai:secret@localhost:5432/javobai"
    embeddings_model: str = "BAAI/bge-m3"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    google_api_key: str = ""
    gemini_fallback_model: str = "gemini-2.0-flash"
    llm_timeout_seconds: float = 15.0

    message_window_hours: int = 24
    outbound_rate_limit_per_second: int = 20

    # Phase 5 — per-conversation anti-runaway guard. A single customer must not
    # be auto-replied to more than this many times per minute.
    outbound_rate_limit_per_conversation_per_minute: int = 3

    # Phase 5 — Redis DLQ for sends that fail after the adapter's retry budget.
    dlq_outbound_key: str = "dlq:outbound"
    dlq_max_entries: int = 1000

    # Phase 5 — Redis pub/sub channel pattern for operator events.
    # Per-tenant handoff events go to: f"handoff:{tenant_id}"
    handoff_event_channel_prefix: str = "handoff"


    # Phase 9 — WhatsApp Cloud API
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = "javobai_wa_verify"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    fernet_key: str = "change_me"

    # Phase 10 — Meta (IG + FB)
    meta_app_secret: str = ""
    meta_verify_token: str = "javobai_meta_verify"

    # Phase 11 — Agentic actions
    action_timeout_seconds: float = 10.0

    @property
    def asyncpg_url(self) -> str:
        """Plain asyncpg DSN (strips SQLAlchemy dialect prefix if present)."""
        return self.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")


worker_settings = WorkerSettings()
settings = worker_settings  # alias for adapters
