"""
TallyChain — Application Configuration
"""
from pydantic_settings import BaseSettings
from pathlib import Path
import os

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TallyChain"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_USE_32_CHAR_MIN"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480          # 8 hours

    # Master DB encryption key (derived from this + PBKDF2)
    DB_MASTER_PASSWORD: str = "TallyChain@SecureDB#2024"
    DB_SALT: str = "TallyChainSalt$9f3a"

    # Paths
    DB_PATH: str = str(DATA_DIR / "tallychain.tdb")      # encrypted DB file
    BLOCKCHAIN_PATH: str = str(DATA_DIR / "ledger.chain") # blockchain file
    AUDIT_PATH: str = str(DATA_DIR / "audit.log")         # audit log

    # CORS
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"]

    class Config:
        env_file = ".env"


settings = Settings()
