from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://javobai:secret@localhost:5432/javobai"
    embeddings_model: str = "BAAI/bge-m3"

    @property
    def asyncpg_url(self) -> str:
        """Plain asyncpg DSN (strips SQLAlchemy dialect prefix if present)."""
        return self.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")


worker_settings = WorkerSettings()
