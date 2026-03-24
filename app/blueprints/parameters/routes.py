from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import ParameterModel, ParameterPrompt, ScanText, TranslationVariant
from ...services.concurrency import bind_version_token, ensure_version_token_matches
from ...services.model_registry import (
    MANUAL_MODEL_NAME,
    MODEL_SCOPE_HTR,
    MODEL_SCOPE_LABELS,
    MODEL_SCOPE_TRANSLATION,
)
from ...services.translation_provider import SUPPORTED_AUTO_TRANSLATION_APIS
from .forms import ParameterModelForm, ParameterPromptForm

parameters_bp = Blueprint("parameters", __name__, template_folder="templates")


def _get_scope_or_404(scope: str) -> str:
    if scope not in MODEL_SCOPE_LABELS:
        from flask import abort

        abort(404)
    return scope


@parameters_bp.route("/")
def index():
    sort_dirs = {
        MODEL_SCOPE_HTR: request.args.get("htr_sort_dir", "asc"),
        MODEL_SCOPE_TRANSLATION: request.args.get("translation_sort_dir", "asc"),
        "prompt": request.args.get("prompt_sort_dir", "asc"),
    }
    for scope in sort_dirs:
        if sort_dirs[scope] not in {"asc", "desc"}:
            sort_dirs[scope] = "asc"

    groups = {}
    for scope, label in MODEL_SCOPE_LABELS.items():
        sort_dir = sort_dirs[scope]
        order = (
            (ParameterModel.name.asc(), ParameterModel.id.asc())
            if sort_dir == "asc"
            else (ParameterModel.name.desc(), ParameterModel.id.asc())
        )
        query = ParameterModel.query.filter_by(scope=scope)
        if scope == MODEL_SCOPE_TRANSLATION:
            query = query.filter(ParameterModel.name != MANUAL_MODEL_NAME)
        groups[scope] = {
            "label": label,
            "sort_dir": sort_dir,
            "entries": query.order_by(*order).all(),
        }
    return render_template(
        "parameters/index.html",
        groups=groups,
        prompts=(
            ParameterPrompt.query.order_by(
                ParameterPrompt.name.asc() if sort_dirs["prompt"] == "asc" else ParameterPrompt.name.desc(),
                ParameterPrompt.id.asc(),
            ).all()
        ),
        prompt_sort_dir=sort_dirs["prompt"],
        manual_model_name=MANUAL_MODEL_NAME,
        htr_scope=MODEL_SCOPE_HTR,
        translation_scope=MODEL_SCOPE_TRANSLATION,
    )


@parameters_bp.route("/models/<scope>/new", methods=["GET", "POST"])
def new_model(scope: str):
    scope = _get_scope_or_404(scope)
    form = ParameterModelForm()
    _configure_model_form(form, scope)
    cancel_url = url_for("parameters.index")
    if form.validate_on_submit():
        name = (form.name.data or "").strip()
        api_definition = _normalize_api_definition(form.api_definition.data if scope == MODEL_SCOPE_TRANSLATION else None)
        model_code = _normalize_model_code(
            form.model_code.data if scope == MODEL_SCOPE_TRANSLATION else None,
            api_definition=api_definition,
        )
        exists = ParameterModel.query.filter_by(scope=scope, name=name).first()
        if not name:
            flash("Nazwa modelu nie może być pusta.", "warning")
        elif exists is not None:
            flash("Taki model już istnieje w tym słowniku.", "warning")
        elif api_definition and api_definition not in SUPPORTED_AUTO_TRANSLATION_APIS:
            flash("Wybrano nieobsługiwaną definicję API.", "warning")
        elif api_definition in {"gemini-api", "openai-api"} and not model_code:
            flash("Dla modeli Gemini i OpenAI podaj kod modelu.", "warning")
        else:
            db.session.add(
                ParameterModel(
                    scope=scope,
                    name=name,
                    api_definition=api_definition,
                    model_code=model_code,
                )
            )
            db.session.commit()
            flash("Dodano model do słownika.", "success")
            return redirect(url_for("parameters.index"))
    return render_template(
        "parameters/form.html",
        form=form,
        title=f"Nowy model: {MODEL_SCOPE_LABELS[scope]}",
        scope=scope,
        scope_label=MODEL_SCOPE_LABELS[scope],
        cancel_url=cancel_url,
    )


@parameters_bp.route("/models/<int:model_id>/edit", methods=["GET", "POST"])
def edit_model(model_id: int):
    model = ParameterModel.query.get_or_404(model_id)
    form = ParameterModelForm(obj=model)
    _configure_model_form(form, model.scope)
    cancel_url = url_for("parameters.index")
    if request.method == "GET":
        bind_version_token(form, model)
    if form.validate_on_submit():
        ensure_version_token_matches(form, model)
        name = (form.name.data or "").strip()
        api_definition = _normalize_api_definition(form.api_definition.data if model.scope == MODEL_SCOPE_TRANSLATION else None)
        model_code = _normalize_model_code(
            form.model_code.data if model.scope == MODEL_SCOPE_TRANSLATION else None,
            api_definition=api_definition,
        )
        exists = (
            ParameterModel.query.filter_by(scope=model.scope, name=name)
            .filter(ParameterModel.id != model.id)
            .first()
        )
        if not name:
            flash("Nazwa modelu nie może być pusta.", "warning")
        elif exists is not None:
            flash("Taki model już istnieje w tym słowniku.", "warning")
        elif api_definition and api_definition not in SUPPORTED_AUTO_TRANSLATION_APIS:
            flash("Wybrano nieobsługiwaną definicję API.", "warning")
        elif api_definition in {"gemini-api", "openai-api"} and not model_code:
            flash("Dla modeli Gemini i OpenAI podaj kod modelu.", "warning")
        else:
            model.name = name
            if model.scope == MODEL_SCOPE_TRANSLATION:
                model.api_definition = api_definition
                model.model_code = model_code
            else:
                model.api_definition = None
                model.model_code = None
            db.session.commit()
            flash("Zapisano model słownikowy.", "success")
            return redirect(url_for("parameters.index"))
    return render_template(
        "parameters/form.html",
        form=form,
        title=f"Edycja modelu: {MODEL_SCOPE_LABELS[model.scope]}",
        scope=model.scope,
        scope_label=MODEL_SCOPE_LABELS[model.scope],
        cancel_url=cancel_url,
    )


def _model_is_in_use(model: ParameterModel) -> bool:
    if model.scope == MODEL_SCOPE_HTR:
        return db.session.query(ScanText.id).filter(ScanText.source_model == model.name).first() is not None
    if model.scope == MODEL_SCOPE_TRANSLATION:
        return (
            db.session.query(TranslationVariant.id)
            .filter(TranslationVariant.source_model == model.name)
            .first()
            is not None
        )
    return False


def _prompt_is_in_use(prompt: ParameterPrompt) -> bool:
    return (
        db.session.query(TranslationVariant.id)
        .filter(TranslationVariant.source_prompt == prompt.name)
        .first()
        is not None
    )


@parameters_bp.route("/models/<int:model_id>/delete", methods=["POST"])
def delete_model(model_id: int):
    model = ParameterModel.query.get_or_404(model_id)
    if model.name == MANUAL_MODEL_NAME:
        flash("Model 'Manualnie' jest wymagany i nie może zostać usunięty.", "warning")
        return redirect(url_for("parameters.index"))
    if _model_is_in_use(model):
        flash("Nie można usunąć modelu, ponieważ jest używany w istniejących wariantach.", "warning")
        return redirect(url_for("parameters.index"))
    db.session.delete(model)
    db.session.commit()
    flash("Usunięto model ze słownika.", "success")
    return redirect(url_for("parameters.index"))


@parameters_bp.route("/prompts/new", methods=["GET", "POST"])
def new_prompt():
    form = ParameterPromptForm()
    cancel_url = url_for("parameters.index")
    if form.validate_on_submit():
        name = (form.name.data or "").strip()
        content = (form.content.data or "").strip()
        exists = ParameterPrompt.query.filter_by(name=name).first()
        if not name:
            flash("Nazwa promptu nie może być pusta.", "warning")
        elif not content:
            flash("Treść promptu nie może być pusta.", "warning")
        elif exists is not None:
            flash("Prompt o tej nazwie już istnieje.", "warning")
        else:
            db.session.add(ParameterPrompt(name=name, content=content))
            db.session.commit()
            flash("Dodano prompt do słownika.", "success")
            return redirect(url_for("parameters.index"))
    return render_template(
        "parameters/prompt_form.html",
        form=form,
        title="Nowy prompt tłumaczenia",
        cancel_url=cancel_url,
    )


@parameters_bp.route("/prompts/<int:prompt_id>/edit", methods=["GET", "POST"])
def edit_prompt(prompt_id: int):
    prompt = ParameterPrompt.query.get_or_404(prompt_id)
    form = ParameterPromptForm(obj=prompt)
    cancel_url = url_for("parameters.index")
    if request.method == "GET":
        bind_version_token(form, prompt)
    if form.validate_on_submit():
        ensure_version_token_matches(form, prompt)
        name = (form.name.data or "").strip()
        content = (form.content.data or "").strip()
        exists = ParameterPrompt.query.filter_by(name=name).filter(ParameterPrompt.id != prompt.id).first()
        if not name:
            flash("Nazwa promptu nie może być pusta.", "warning")
        elif not content:
            flash("Treść promptu nie może być pusta.", "warning")
        elif exists is not None:
            flash("Prompt o tej nazwie już istnieje.", "warning")
        else:
            old_name = prompt.name
            prompt.name = name
            prompt.content = content
            if old_name != name:
                variants = TranslationVariant.query.filter_by(source_prompt=old_name).all()
                for variant in variants:
                    variant.source_prompt = name
            db.session.commit()
            flash("Zapisano prompt.", "success")
            return redirect(url_for("parameters.index"))
    return render_template(
        "parameters/prompt_form.html",
        form=form,
        title="Edycja promptu tłumaczenia",
        cancel_url=cancel_url,
    )


@parameters_bp.route("/prompts/<int:prompt_id>/delete", methods=["POST"])
def delete_prompt(prompt_id: int):
    prompt = ParameterPrompt.query.get_or_404(prompt_id)
    if _prompt_is_in_use(prompt):
        flash("Nie można usunąć promptu, ponieważ jest używany w istniejących wariantach.", "warning")
        return redirect(url_for("parameters.index"))
    db.session.delete(prompt)
    db.session.commit()
    flash("Usunięto prompt ze słownika.", "success")
    return redirect(url_for("parameters.index"))


def _configure_model_form(form: ParameterModelForm, scope: str) -> None:
    if scope != MODEL_SCOPE_TRANSLATION:
        form.api_definition.choices = [("", "- nie dotyczy -")]
        if not form.is_submitted():
            form.api_definition.data = ""
            form.model_code.data = ""


def _normalize_api_definition(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _normalize_model_code(value: str | None, *, api_definition: str | None = None) -> str | None:
    if api_definition not in {"gemini-api", "openai-api"}:
        return None
    normalized = (value or "").strip()
    return normalized or None
