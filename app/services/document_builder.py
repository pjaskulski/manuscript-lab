def build_document_text_from_scan_texts(scan_texts: list[str]) -> str:
    cleaned = [text.strip() for text in scan_texts if text and text.strip()]
    return "\n\n".join(cleaned)
