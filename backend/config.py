"""Configuration management for Finalyzer."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Parser configuration
    use_generic_parser: bool = False  # Feature flag for LLM-based generic parser

    # Data directory
    data_dir: Path = Path.home() / ".finalyzer"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # LLM_PROVIDER and llm_provider both work
        extra="ignore",  # Ignore extra environment variables
    )

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

    def log_config(self) -> None:
        """Log current configuration with sensitive values redacted."""
        import os

        print("\n" + "=" * 60)
        print("📋 CONFIGURATION LOADED")
        print("=" * 60)

        # Check if values come from environment or .env file
        env_llm_provider = os.getenv("LLM_PROVIDER")
        env_file_path = os.path.join(os.getcwd(), ".env")

        print(f"Working Directory:   {os.getcwd()}")
        print(f".env file exists:    {os.path.exists(env_file_path)}")

        # Read .env file to show what it contains
        if os.path.exists(env_file_path):
            with open(env_file_path) as f:
                for line in f:
                    if line.startswith("LLM_PROVIDER"):
                        print(f".env file contains:  {line.strip()}")
                        break

        if env_llm_provider:
            print(f"⚠️  ENV VAR override:   LLM_PROVIDER={env_llm_provider}")
        print("-" * 60)

        print(f"LLM Provider:        {self.llm_provider}")
        print(
            f"OpenAI API Key:      {'✓ Set (' + self.openai_api_key[:8] + '...' + self.openai_api_key[-4:] + ')' if self.openai_api_key else '✗ Not set'}"
        )
        print(f"OpenAI Model:        {self.openai_model}")
        print(f"Ollama Host:         {self.ollama_host}")
        print(f"Ollama Model:        {self.ollama_model}")
        print(f"Embedding Model:     {self.embedding_model}")
        print(f"Dev Mode:            {self.dev_mode}")
        print(f"Use Generic Parser:  {self.use_generic_parser}")
        print(f"Data Directory:      {self.data_dir}")
        print(f"Database:            {self.db_path}")
        print(f"Vector Store:        {self.chroma_path}")
        print(f"API Host:            {self.api_host}:{self.api_port}")
        print("=" * 60 + "\n")


# Global settings instance
settings = Settings()
