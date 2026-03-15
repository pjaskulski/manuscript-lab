from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import ParameterModel, ScanText, TranslationVariant
from ...services.concurrency import bind_version_token, ensure_version_token_matches
from ...services.model_registry import (
    MANUAL_MODEL_NAME,
    MODEL_SCOPE_HTR,
    MODEL_SCOPE_LABELS,
    MODEL_SCOPE_TRANSLATION,
)
from .forms import ParameterModelForm

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
        groups[scope] = {
            "label": label,
            "sort_dir": sort_dir,
            "entries": (
                ParameterModel.query.filter_by(scope=scope)
                .order_by(*order)
                .all()
            ),
        }
    return render_template(
        "parameters/index.html",
        groups=groups,
        manual_model_name=MANUAL_MODEL_NAME,
        htr_scope=MODEL_SCOPE_HTR,
        translation_scope=MODEL_SCOPE_TRANSLATION,
    )


@parameters_bp.route("/models/<scope>/new", methods=["GET", "POST"])
def new_model(scope: str):
    scope = _get_scope_or_404(scope)
    form = ParameterModelForm()
    cancel_url = url_for("parameters.index")
    if form.validate_on_submit():
        name = (form.name.data or "").strip()
        exists = ParameterModel.query.filter_by(scope=scope, name=name).first()
        if not name:
            flash("Nazwa modelu nie może być pusta.", "warning")
        elif exists is not None:
            flash("Taki model już istnieje w tym słowniku.", "warning")
        else:
            db.session.add(ParameterModel(scope=scope, name=name))
            db.session.commit()
            flash("Dodano model do słownika.", "success")
            return redirect(url_for("parameters.index"))
    return render_template(
        "parameters/form.html",
        form=form,
        title=f"Nowy model: {MODEL_SCOPE_LABELS[scope]}",
        scope_label=MODEL_SCOPE_LABELS[scope],
        cancel_url=cancel_url,
    )


@parameters_bp.route("/models/<int:model_id>/edit", methods=["GET", "POST"])
def edit_model(model_id: int):
    model = ParameterModel.query.get_or_404(model_id)
    form = ParameterModelForm(obj=model)
    cancel_url = url_for("parameters.index")
    if request.method == "GET":
        bind_version_token(form, model)
    if form.validate_on_submit():
        ensure_version_token_matches(form, model)
        name = (form.name.data or "").strip()
        exists = (
            ParameterModel.query.filter_by(scope=model.scope, name=name)
            .filter(ParameterModel.id != model.id)
            .first()
        )
        if not name:
            flash("Nazwa modelu nie może być pusta.", "warning")
        elif exists is not None:
            flash("Taki model już istnieje w tym słowniku.", "warning")
        else:
            model.name = name
            db.session.commit()
            flash("Zapisano model słownikowy.", "success")
            return redirect(url_for("parameters.index"))
    return render_template(
        "parameters/form.html",
        form=form,
        title=f"Edycja modelu: {MODEL_SCOPE_LABELS[model.scope]}",
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
