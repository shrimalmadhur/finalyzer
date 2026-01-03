"""Configuration management for Finalyzer."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    llm_provider: Literal["ollama", "openai"] = "ollama"
    openai_api_key: str = ""
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_model: str = "gpt-4o-mini"

    # Embedding model
    embedding_model: str = "nomic-embed-text"

    # Development mode
    dev_mode: bool = True

    # Data directory
    data_dir: Path = Path.home() / ".finalyzer"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def db_path(self) -> Path:
        """Get the SQLite database path."""
        suffix = "dev" if self.dev_mode else "prod"
        return self.data_dir / f"finalyzer_{suffix}.db"

    @property
    def chroma_path(self) -> Path:
        """Get the ChromaDB storage path."""
        suffix = "dev" if self.dev_mode else "prod"
        return self.data_dir / f"chroma_{suffix}"

    @property
    def uploads_path(self) -> Path:
        """Get the uploads directory path."""
        return self.data_dir / "uploads"

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_path.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
