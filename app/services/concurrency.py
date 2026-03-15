from __future__ import annotations

from datetime import datetime


class ConcurrentUpdateError(RuntimeError):
    pass


def version_token_for(model) -> str:
    updated_at = getattr(model, "updated_at", None)
    if updated_at is None:
        return ""
    return updated_at.isoformat()


def bind_version_token(form, model) -> None:
    if hasattr(form, "version_token"):
        form.version_token.data = version_token_for(model)


def ensure_version_token_matches(form, model) -> None:
    if not hasattr(form, "version_token"):
        return

    submitted_token = (form.version_token.data or "").strip()
    current_token = version_token_for(model)
    if submitted_token and submitted_token != current_token:
        raise ConcurrentUpdateError("Ten rekord został zmieniony przez innego użytkownika. Odśwież formularz i spróbuj ponownie.")
