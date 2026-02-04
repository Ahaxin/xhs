"""
Configuration management using Pydantic settings.
"""
from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings
import yaml


class XiaohongshuConfig(BaseSettings):
    """Xiaohongshu-specific configuration."""
    creator_center_url: str = "https://creator.xiaohongshu.com"
    login_method: Literal["sms", "qr_code"] = "sms"
    session_file: str = "data/xhs_session.json"
    phone_number: str = ""


class ContentFetchingConfig(BaseSettings):
    """Content fetching configuration."""
    enabled: bool = False
    source_url: str = ""
    schedule: str = "0 */6 * * *"
    max_items: int = 10


class PublishingConfig(BaseSettings):
    """Publishing configuration."""
    mode: Literal["approval", "auto"] = "approval"
    max_posts_per_day: int = 3
    retry_attempts: int = 3
    retry_delay: int = 60
    human_delay_min: int = 2
    human_delay_max: int = 5


class UIConfig(BaseSettings):
    """UI configuration."""
    host: str = "127.0.0.1"
    port: int = 5000
    debug: bool = True


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    path: str = "data/xhs.db"


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    level: str = "INFO"
    file: str = "logs/xhs.log"
    rotation: str = "10 MB"
    retention: str = "7 days"


class Config(BaseSettings):
    """Main application configuration."""
    xiaohongshu: XiaohongshuConfig = Field(default_factory=XiaohongshuConfig)
    content_fetching: ContentFetchingConfig = Field(default_factory=ContentFetchingConfig)
    publishing: PublishingConfig = Field(default_factory=PublishingConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def load_from_yaml(cls, config_path: str = "config/config.yaml") -> "Config":
        """Load configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        return cls(
            xiaohongshu=XiaohongshuConfig(**data.get("xiaohongshu", {})),
            content_fetching=ContentFetchingConfig(**data.get("content_fetching", {})),
            publishing=PublishingConfig(**data.get("publishing", {})),
            ui=UIConfig(**data.get("ui", {})),
            database=DatabaseConfig(**data.get("database", {})),
            logging=LoggingConfig(**data.get("logging", {})),
        )


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load_from_yaml()
    return _config


def reload_config() -> Config:
    """Reload configuration from file."""
    global _config
    _config = Config.load_from_yaml()
    return _config
