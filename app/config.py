import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    DEFAULT_MAX_CONTENT_LENGTH = 250 * 1024 * 1024
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_ALIGNMENT_MODEL = os.environ.get("GEMINI_ALIGNMENT_MODEL", "gemini-3.1-pro-preview")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    TRANSLATION_SOURCE_LANGUAGE = os.environ.get("TRANSLATION_SOURCE_LANGUAGE")
    TRANSLATION_TARGET_LANGUAGE = os.environ.get("TRANSLATION_TARGET_LANGUAGE", "PL")
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
    THUMBNAIL_FOLDER = (INSTANCE_DIR / "uploads" / "scans" / "thumbs").as_posix()
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", DEFAULT_MAX_CONTENT_LENGTH))
