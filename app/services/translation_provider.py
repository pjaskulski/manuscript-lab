from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx
from flask import current_app
from google import genai
from google.genai import types
from openai import APITimeoutError, OpenAI

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
    TRANSLATION_API_GEMINI,
    TRANSLATION_API_OPENAI,
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
    elapsed_ms: int | None = None


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
        started_at = time.perf_counter()
        translated_text = _translate_with_deepl(content)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    elif api_definition == TRANSLATION_API_GOOGLE:
        started_at = time.perf_counter()
        translated_text = _translate_with_google(content)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    elif api_definition == TRANSLATION_API_GEMINI:
        started_at = time.perf_counter()
        translated_text = _translate_with_gemini(
            text=content,
            model_code=(model.model_code or "").strip(),
            prompt_name=prompt_name,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    elif api_definition == TRANSLATION_API_OPENAI:
        started_at = time.perf_counter()
        translated_text = _translate_with_openai(
            text=content,
            model_code=(model.model_code or "").strip(),
            prompt_name=prompt_name,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    else:
        raise TranslationProviderError("Wybrany model nie obsługuje automatycznego tłumaczenia.")

    prompt_name = (prompt_name or "").strip()
    if prompt_name:
        prompt = ParameterPrompt.query.filter_by(name=prompt_name).first()
        if prompt is None:
            raise TranslationProviderError("Wybrany prompt tłumaczenia nie istnieje.")

    source_tool = get_api_label(api_definition) or api_definition
    return TranslationResult(text=translated_text, source_tool=source_tool, elapsed_ms=elapsed_ms)


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


def _translate_with_gemini(text: str, model_code: str, prompt_name: str | None) -> str:
    api_key = (current_app.config.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise TranslationProviderError("Brak klucza GEMINI_API_KEY w konfiguracji aplikacji.")
    if not model_code:
        raise TranslationProviderError("Model Gemini nie ma skonfigurowanego kodu modelu.")

    prompt_payload = _build_translation_prompt_payload(text=text, prompt_name=prompt_name)

    timeout_seconds = _provider_timeout_seconds()
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
    )
    try:
        response = client.models.generate_content(
            model=model_code,
            contents=prompt_payload.user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=prompt_payload.system_prompt,
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    except httpx.TimeoutException as exc:
        raise TranslationProviderError(
            f"Gemini nie odpowiedział w czasie {timeout_seconds} s. Skróć tekst, wybierz szybszy model albo zwiększ limit czasu."
        ) from exc

    translated_text = (response.text or "").strip()
    if not translated_text:
        raise TranslationProviderError("Model Gemini nie zwrócił tłumaczenia.")
    return translated_text


def _translate_with_openai(text: str, model_code: str, prompt_name: str | None) -> str:
    api_key = (current_app.config.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise TranslationProviderError("Brak klucza OPENAI_API_KEY w konfiguracji aplikacji.")
    if not model_code:
        raise TranslationProviderError("Model OpenAI nie ma skonfigurowanego kodu modelu.")

    prompt_payload = _build_translation_prompt_payload(text=text, prompt_name=prompt_name)

    timeout_seconds = _provider_timeout_seconds()
    client = OpenAI(api_key=api_key, timeout=timeout_seconds)
    try:
        response = client.responses.create(
            model=model_code,
            temperature=0.2,
            instructions=prompt_payload.system_prompt,
            input=prompt_payload.user_prompt,
        )
    except APITimeoutError as exc:
        raise TranslationProviderError(
            f"OpenAI nie odpowiedział w czasie {timeout_seconds} s. Skróć tekst, wybierz szybszy model albo zwiększ limit czasu."
        ) from exc

    translated_text = (response.output_text or "").strip()
    if not translated_text:
        raise TranslationProviderError("Model OpenAI nie zwrócił tłumaczenia.")
    return translated_text


def _provider_timeout_seconds() -> int:
    configured = current_app.config.get("TRANSLATION_PROVIDER_TIMEOUT_SECONDS", 25)
    try:
        timeout = int(configured)
    except (TypeError, ValueError):
        timeout = 25
    return max(1, timeout)


@dataclass(slots=True)
class TranslationPromptPayload:
    system_prompt: str
    user_prompt: str


def _resolve_translation_prompt(prompt_name: str | None) -> str | None:
    normalized_name = (prompt_name or "").strip()
    if not normalized_name:
        return None
    prompt = ParameterPrompt.query.filter_by(name=normalized_name).first()
    if prompt is None:
        raise TranslationProviderError("Wybrany prompt tłumaczenia nie istnieje.")
    content = (prompt.content or "").strip()
    if not content:
        raise TranslationProviderError("Wybrany prompt tłumaczenia jest pusty.")
    return content


def _build_translation_prompt_payload(*, text: str, prompt_name: str | None) -> TranslationPromptPayload:
    prompt = _resolve_translation_prompt(prompt_name)
    source_lang = (current_app.config.get("TRANSLATION_SOURCE_LANGUAGE") or "").strip() or "auto"
    target_lang = (current_app.config.get("TRANSLATION_TARGET_LANGUAGE") or "PL").strip() or "PL"

    system_instructions = [
        "Jestes tlumaczem dokumentow historycznych.",
        "Przetlumacz tekst wiernie, kompletnie i bez skracania.",
        f"Jezyk zrodlowy: {source_lang}.",
        f"Jezyk docelowy: {target_lang}.",
        "Zachowaj podzial na akapity i wiersze, o ile instrukcje dodatkowe nie wymagaja inaczej.",
        "Nie dodawaj komentarzy, przypisow, wyjasnien ani naglowkow.",
        "Zwroc wylacznie gotowe tlumaczenie.",
    ]
    if prompt:
        system_instructions.extend(
            [
                "",
                "Dodatkowe instrukcje:",
                prompt,
            ]
        )
    user_prompt = "\n".join(
        [
            "Tekst do przetlumaczenia:",
            text,
        ]
    )
    return TranslationPromptPayload(
        system_prompt="\n".join(system_instructions),
        user_prompt=user_prompt,
    )
