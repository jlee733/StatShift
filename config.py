from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_root: Path = Path(__file__).resolve().parent
    db_path: Path = project_root / "data" / "statshift.db"
    espn_letter_cache_dir: Path = project_root / "data" / "espn_active_by_letter"
    espn_active_players_full_path: Path = project_root / "data" / "espn_active_players_full.json"
    api_base_url: str = "http://127.0.0.1:8000"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma2:2b"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    espn_api_delay_seconds: float = 30.0


settings = Settings()
