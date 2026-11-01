from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_LLM_MODEL: str = "llama3.1:8b"

    # SQL Server
    DB_SERVER: str = r"localhost\SQLEXPRESS"
    DB_BUSINESS: str = "Db_QuyChe_Business"
    DB_VECTOR: str = "Db_QuyChe_Vector"
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"

    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None

    DB_WINDOWS_AUTH: bool = True
    DB_TRUST_SERVER_CERTIFICATE: str = "yes"
    DB_ENCRYPT: str = "yes"

    # Trusted upstream HS256 bearer-token validation
    AUTH_JWT_SECRET: Optional[str] = None
    AUTH_JWT_ISSUER: Optional[str] = None
    AUTH_JWT_AUDIENCE: Optional[str] = None
    AUTH_JWT_MAX_TTL_SECONDS: int = 3600

    model_config = SettingsConfigDict(
        env_file=BACKEND_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()
