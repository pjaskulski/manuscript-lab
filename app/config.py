from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    SECRET_KEY = "dev-secret-key-change-me"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{(INSTANCE_DIR / 'app.db').as_posix()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = (INSTANCE_DIR / "uploads" / "scans").as_posix()
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
