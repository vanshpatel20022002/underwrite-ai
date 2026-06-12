from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "underwriting"
    postgres_password: str = "underwriting"
    postgres_db: str = "underwriting"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    vertex_project_id: str = ""
    vertex_location: str = "us-central1"
    llm_provider: str = "vertex"
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    # Groq — OpenAI-compatible endpoint. Accepts GROQ_API_KEY or GROQ_KEY env var.
    groq_api_key: str = ""
    groq_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    confidence_threshold: float = 0.65
    upload_dir: str = "./uploads"
    data_dir: str = "./data"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
