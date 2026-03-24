from __future__ import annotations

import asyncio
from dataclasses import dataclass

from flask import current_app

from ..models.parameter import ParameterModel, ParameterPrompt

TRANSLATION_API_DEEPL = "deepl-api"
TRANSLATION_API_GOOGLE = "google-translate"
TRANSLATION_API_GEMINI = "gemini-api"
TRANSLATION_API_OPENAI = "openai-api"

SUPPORTED_AUTO_TRANSLATION_APIS = {
    TRANSLATION_API_DEEPL,
    TRANSLATION_API_GOOGLE,
    TRANSLATION_API_GEMINI,
    TRANSLATION_API_OPENAI,
}

AUTO_TRANSLATION_ACTIVE_APIS = {
    TRANSLATION_API_DEEPL,
    TRANSLATION_API_GOOGLE,
}

API_LABELS = {
    TRANSLATION_API_DEEPL: "DeepL API",
    TRANSLATION_API_GOOGLE: "Google Translate",
    TRANSLATION_API_GEMINI: "Gemini API",
    TRANSLATION_API_OPENAI: "OpenAI API",
}


class TranslationProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class TranslationResult:
    text: str
    source_tool: str


def get_api_label(api_definition: str | None) -> str | None:
    normalized = (api_definition or "").strip()
    return API_LABELS.get(normalized) if normalized else None


def supports_auto_translation(model: ParameterModel | None) -> bool:
    if model is None:
        return False
    api_definition = (model.api_definition or "").strip()
    return api_definition in AUTO_TRANSLATION_ACTIVE_APIS


def translate_document_text(
    *,
    model: ParameterModel,
    source_text: str,
    prompt_name: str | None = None,
) -> TranslationResult:
    if model.scope != "translation":
        raise TranslationProviderError("Wybrany model nie należy do słownika modeli tłumaczeń.")

    content = (source_text or "").strip()
    if not content:
        raise TranslationProviderError("Dokument nie ma tekstu źródłowego do przetłumaczenia.")

    api_definition = (model.api_definition or "").strip()
    if api_definition == TRANSLATION_API_DEEPL:
        translated_text = _translate_with_deepl(content)
    elif api_definition == TRANSLATION_API_GOOGLE:
        translated_text = _translate_with_google(content)
    elif api_definition in {TRANSLATION_API_GEMINI, TRANSLATION_API_OPENAI}:
        raise TranslationProviderError("Ten typ API jest już przygotowany konfiguracyjnie, ale nie został jeszcze zaimplementowany.")
    else:
        raise TranslationProviderError("Wybrany model nie obsługuje automatycznego tłumaczenia.")

    prompt_name = (prompt_name or "").strip()
    if prompt_name:
        prompt = ParameterPrompt.query.filter_by(name=prompt_name).first()
        if prompt is None:
            raise TranslationProviderError("Wybrany prompt tłumaczenia nie istnieje.")

    source_tool = get_api_label(api_definition) or api_definition
    return TranslationResult(text=translated_text, source_tool=source_tool)


def _translate_with_deepl(text: str) -> str:
    api_key = (current_app.config.get("DEEPL_API_KEY") or "").strip()
    if not api_key:
        raise TranslationProviderError("Brak klucza DEEPL_API_KEY w konfiguracji aplikacji.")

    try:
        import deepl
    except ImportError as exc:
        raise TranslationProviderError("Biblioteka 'deepl' nie jest zainstalowana.") from exc

    target_lang = (current_app.config.get("TRANSLATION_TARGET_LANGUAGE") or "PL").strip() or "PL"
    source_lang = (current_app.config.get("TRANSLATION_SOURCE_LANGUAGE") or "").strip() or None
    translator = deepl.Translator(api_key)
    result = translator.translate_text(text, source_lang=source_lang, target_lang=target_lang)
    return (getattr(result, "text", None) or "").strip()


def _translate_with_google(text: str) -> str:
    try:
        from googletrans import Translator
    except ImportError as exc:
        message = str(exc)
        if "ProxiesTypes" in message and "httpx._types" in message:
            raise TranslationProviderError(
                "Biblioteka 'googletrans' jest zainstalowana, ale niekompatybilna z obecną wersją 'httpx'."
            ) from exc
        raise TranslationProviderError("Biblioteka 'googletrans' nie jest zainstalowana.") from exc

    target_lang = (current_app.config.get("TRANSLATION_TARGET_LANGUAGE") or "pl").strip() or "pl"
    source_lang = (current_app.config.get("TRANSLATION_SOURCE_LANGUAGE") or "").strip() or "auto"
    result = asyncio.run(_run_google_translation(text, source_lang, target_lang.lower(), Translator))
    return (getattr(result, "text", None) or "").strip()


async def _run_google_translation(text: str, source_lang: str, target_lang: str, translator_class):
    async with translator_class() as translator:
        return await translator.translate(text, src=source_lang, dest=target_lang)
