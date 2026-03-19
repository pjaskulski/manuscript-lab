from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "tif", "tiff"}
THUMBNAIL_MAX_WIDTH = 800
THUMBNAIL_SUBDIR = "thumbs"


def thumbnail_filename_for(image_path: str) -> str:
    original_path = Path(image_path)
    return f"{original_path.stem}_thumb.jpg"


def thumbnail_relative_path_for(image_path: str) -> str:
    return f"{THUMBNAIL_SUBDIR}/{thumbnail_filename_for(image_path)}"


def ensure_scan_thumbnail(image_path: str, upload_dir: str, max_width: int = THUMBNAIL_MAX_WIDTH) -> str | None:
    if not image_path:
        return None

    upload_root = Path(upload_dir)
    source = upload_root / image_path
    if not source.exists():
        return None

    thumbnail_relative_path = thumbnail_relative_path_for(image_path)
    target = upload_root / thumbnail_relative_path
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(source) as img:
            prepared = ImageOps.exif_transpose(img)
            if prepared.mode not in {"RGB", "L"}:
                prepared = prepared.convert("RGB")
            elif prepared.mode == "L":
                prepared = prepared.convert("RGB")

            if prepared.width > max_width:
                ratio = max_width / prepared.width
                target_height = max(1, int(prepared.height * ratio))
                prepared = prepared.resize((max_width, target_height), Image.Resampling.LANCZOS)

            prepared.save(target, format="JPEG", quality=82, optimize=True)
    except Exception:
        return None

    return thumbnail_relative_path


def save_scan_image(file: FileStorage, upload_dir: str) -> dict:
    if not file or not file.filename:
        return {"image_path": None, "image_width": None, "image_height": None, "thumbnail_path": None}

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

    thumbnail_path = ensure_scan_thumbnail(filename, upload_dir)

    return {
        "image_path": filename,
        "image_width": width,
        "image_height": height,
        "thumbnail_path": thumbnail_path,
    }
