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

    @property
    def asyncpg_url(self) -> str:
        """Plain asyncpg DSN (strips SQLAlchemy dialect prefix if present)."""
        return self.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")


worker_settings = WorkerSettings()
