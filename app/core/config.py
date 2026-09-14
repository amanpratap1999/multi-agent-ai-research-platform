from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project metadata
    PROJECT_NAME: str = "Multi-Agent AI Research Platform"
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"]
    )

    # PostgreSQL / pgvector
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="research_db")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis STM & Streams
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str | None = Field(default=None)

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # AWS Bedrock Guardrails
    AWS_REGION: str = Field(default="us-east-1")
    AWS_ACCESS_KEY_ID: str | None = Field(default=None)
    AWS_SECRET_ACCESS_KEY: str | None = Field(default=None)
    BEDROCK_GUARDRAIL_ID: str | None = Field(default=None)
    BEDROCK_GUARDRAIL_VERSION: str = Field(default="DRAFT")
    USE_BEDROCK_MOCK: bool = Field(default=False)

    # LLM Providers & Gateway
    OPENAI_API_KEY: str | None = Field(default=None)
    GROQ_API_KEY: str | None = Field(default=None)
    PRIMARY_MODEL: str = Field(default="gpt-4o")
    FALLBACK_MODEL_1: str = Field(default="groq/llama-3.3-70b-versatile")
    FALLBACK_MODEL_2: str = Field(default="bedrock/anthropic.claude-3-5-sonnet")

    # Search Provider
    SEARCH_PROVIDER: str = Field(default="duckduckgo")  # "duckduckgo" or "tavily"
    TAVILY_API_KEY: str | None = Field(default=None)
    MAX_SEARCH_RESULTS: int = Field(default=5)

    # Semantic Cache
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = Field(default=0.95)
    SEMANTIC_CACHE_WRITE_GATE_SCORE: float = Field(default=0.90)
    SEMANTIC_CACHE_TTL_HOURS: int = Field(default=72)
    EMBEDDING_MODEL_NAME: str = Field(default="BAAI/bge-small-en-v1.5")
    EMBEDDING_DIMENSION: int = Field(default=384)

    # LangSmith / Observability
    LANGCHAIN_TRACING_V2: bool = Field(default=False)
    LANGCHAIN_API_KEY: str | None = Field(default=None)
    LANGCHAIN_PROJECT: str = Field(default="multi-agent-research")


settings = Settings()
