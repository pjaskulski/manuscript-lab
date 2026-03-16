import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_ALIGNMENT_MODEL = os.environ.get("GEMINI_ALIGNMENT_MODEL", "gemini-3.1-pro-preview")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{(INSTANCE_DIR / 'app.db').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "timeout": 30,
        },
    }
    UPLOAD_FOLDER = (INSTANCE_DIR / "uploads" / "scans").as_posix()
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
