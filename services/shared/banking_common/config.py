from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://banking:banking@localhost:5432/banking"
    kafka_bootstrap_servers: str = "localhost:29092"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    rate_limit_per_minute: int = 120
    fraud_threshold: float = 0.85
    fraud_model_path: str = "models/fraud_isolation_forest.joblib"
    max_document_upload_bytes: int = 5 * 1024 * 1024
    zipkin_endpoint: str = "http://localhost:9411/api/v2/spans"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
