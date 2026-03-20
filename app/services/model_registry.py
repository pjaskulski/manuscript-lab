from ..models.parameter import ParameterModel, ParameterPrompt

MODEL_SCOPE_HTR = "htr"
MODEL_SCOPE_TRANSLATION = "translation"
MANUAL_MODEL_NAME = "Manualnie"

MODEL_SCOPE_LABELS = {
    MODEL_SCOPE_HTR: "Modele HTR",
    MODEL_SCOPE_TRANSLATION: "Modele tłumaczeń",
}


def get_model_choices(scope: str, current_value: str | None = None) -> list[tuple[str, str]]:
    entries = (
        ParameterModel.query.filter_by(scope=scope)
        .order_by(ParameterModel.name.asc(), ParameterModel.id.asc())
        .all()
    )
    choices = [(entry.name, entry.name) for entry in entries]
    value = (current_value or "").strip()
    if value and value not in {name for name, _label in choices}:
        choices.insert(0, (value, f"{value} (istniejąca wartość)"))
    return choices


def get_prompt_choices(current_value: str | None = None, include_empty: bool = True) -> list[tuple[str, str]]:
    entries = ParameterPrompt.query.order_by(ParameterPrompt.name.asc(), ParameterPrompt.id.asc()).all()
    choices = [(entry.name, entry.name) for entry in entries]
    value = (current_value or "").strip()
    if value and value not in {name for name, _label in choices}:
        choices.insert(0, (value, f"{value} (istniejąca wartość)"))
    if include_empty:
        choices.insert(0, ("", "- brak -"))
    return choices
