from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()
