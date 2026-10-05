import io
import string
import zipfile
from collections.abc import Iterable
from pathlib import Path


def _original_scan_filename(filename: str) -> str:
    prefix, separator, rest = filename.partition("_")
    if separator and len(prefix) == 32 and all(char in string.hexdigits for char in prefix):
        return rest
    return filename


def _unique_archive_name(name: str, used_names: set[str]) -> str:
    candidate = name
    stem = Path(name).stem
    suffix = Path(name).suffix
    counter = 2
    while candidate in used_names:
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    used_names.add(candidate)
    return candidate


def build_scan_export_archive(
    scan_texts: Iterable[tuple[str, str]],
    upload_dir: Path,
    *,
    include_images: bool,
) -> io.BytesIO:
    archive_buffer = io.BytesIO()
    used_names: set[str] = set()

    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for stored_image_path, content in scan_texts:
            original_image_name = _original_scan_filename(Path(stored_image_path).name)
            text_name = _unique_archive_name(f"{Path(original_image_name).stem}.txt", used_names)
            archive.writestr(text_name, content)

            if include_images:
                image_path = upload_dir / stored_image_path
                if image_path.is_file():
                    image_name = _unique_archive_name(original_image_name, used_names)
                    archive.write(image_path, arcname=image_name)

    archive_buffer.seek(0)
    return archive_buffer
