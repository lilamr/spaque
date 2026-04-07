"""
config.py — Centralized app configuration via .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")


class DatabaseConfig:
    HOST: str = os.getenv("DB_HOST", "localhost")
    PORT: int = int(os.getenv("DB_PORT", "5432"))
    NAME: str = os.getenv("DB_NAME", "")
    USER: str = os.getenv("DB_USER", "postgres")
    PASSWORD: str = os.getenv("DB_PASSWORD", "")

    @classmethod
    def dsn(cls) -> str:
        return (
            f"postgresql+psycopg2://{cls.USER}:{cls.PASSWORD}"
            f"@{cls.HOST}:{cls.PORT}/{cls.NAME}"
        )


class AppConfig:
    LOG_LEVEL: str = os.getenv("APP_LOG_LEVEL", "INFO")
    MAX_FEATURES: int = int(os.getenv("APP_MAX_FEATURES", "10000"))
    DEFAULT_SRID: int = int(os.getenv("APP_DEFAULT_SRID", "4326"))
    APP_NAME: str = "Spaque"
    APP_VERSION: str = "1.0.0"
    APP_DIR: Path = Path(__file__).parent


class UIConfig:
    WINDOW_MIN_WIDTH: int = 1100
    WINDOW_MIN_HEIGHT: int = 650
    DEFAULT_WIDTH: int = 1440
    DEFAULT_HEIGHT: int = 880
    LEFT_PANEL_WIDTH: int = 270
    BOTTOM_PANEL_HEIGHT: int = 260
    COLORMAP_DEFAULT: str = "viridis"
