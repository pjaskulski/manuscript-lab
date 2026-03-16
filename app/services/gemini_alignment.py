from __future__ import annotations

from pathlib import Path

from google import genai
from google.genai import types


class GeminiAlignmentError(RuntimeError):
    pass


def align_transcription_lines(
    *,
    api_key: str | None,
    model: str,
    image_path: Path,
    raw_text: str,
) -> str:
    if not api_key:
        raise GeminiAlignmentError("Brak klucza GEMINI_API_KEY w konfiguracji środowiska.")
    if not raw_text.strip():
        raise GeminiAlignmentError("Brak tekstu do dopasowania.")
    if not image_path.exists():
        raise GeminiAlignmentError("Nie znaleziono pliku obrazu skanu.")

    image_bytes = image_path.read_bytes()
    mime_type = _mime_type_for_path(image_path)
    client = genai.Client(api_key=api_key)

    prompt = (
        "Jestes ekspertem paleografem. Otrzymujesz skan rekopisu oraz surową transkrypcję bez podziału na wiersze. "
        "Twoim zadaniem jest zwrocić dokladnie ten sam tekst, ale ulozony w wiersze analogicznie do układu widocznego na skanie. "
        "Jeśli przekazany tekst zawiera więcej treści niż widoczna na skanie, uwzględnij tylko ten fragment, który da sie powiazac z obrazem. "
        "Nie dodawaj komentarzy, nie numeruj wierszy, nie poprawiaj treści, nie modernizuj pisowni. "
        "Zwracaj tylko gotowy tekst z podziałem na wiersze.\n\n"
        f"Tekst do ułożenia:\n{raw_text}"
    )

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=types.GenerateContentConfig(
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )

    formatted_text = (response.text or "").strip()
    if not formatted_text:
        raise GeminiAlignmentError("Model nie zwrócił tekstu.")
    return formatted_text


def _mime_type_for_path(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix in {".tif", ".tiff"}:
        return "image/tiff"
    return "application/octet-stream"
