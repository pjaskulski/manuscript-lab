import re


def normalize_text(text: str, profile: str = "lowercase") -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = text.strip()

    if profile in {"lowercase", "lowercase_no_punct"}:
        text = text.lower()
    if profile == "lowercase_no_punct":
        text = re.sub(r"[^\w\s\n]", "", text, flags=re.UNICODE)
        text = re.sub(r"[ ]+", " ", text).strip()

    return text
