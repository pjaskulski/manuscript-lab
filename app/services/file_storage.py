from pathlib import Path
from uuid import uuid4

from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "tif", "tiff"}


def save_scan_image(file: FileStorage, upload_dir: str) -> dict:
    if not file or not file.filename:
        return {"image_path": None, "image_width": None, "image_height": None}

    original = secure_filename(file.filename)
    suffix = Path(original).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Niedozwolony format pliku.")

    filename = f"{uuid4().hex}_{original}"
    target = Path(upload_dir) / filename
    file.save(target)

    width = height = None
    try:
        with Image.open(target) as img:
            width, height = img.size
    except Exception:
        pass

    return {
        "image_path": filename,
        "image_width": width,
        "image_height": height,
    }
