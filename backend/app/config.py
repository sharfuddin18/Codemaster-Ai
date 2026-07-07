"""Configuration and environment variable management."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Ollama
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_TIMEOUT: float = 300.0  # 5 minutes

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # Generation defaults
    GENERATION_TEMPERATURE: float = 0.1
    GENERATION_TOP_P: float = 0.9
    GENERATION_TOP_K: int = 40
    GENERATION_TIMEOUT: float = 300.0  # 5 minutes

    # Request validation
    MAX_PROMPT_LENGTH: int = 5000
    MAX_CODE_LENGTH: int = 50000

    # API
    API_KEY: str = ""  # Optional API key for authentication


settings = Settings()
