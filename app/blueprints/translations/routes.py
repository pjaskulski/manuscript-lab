import csv
import io
from collections import defaultdict

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from openpyxl import Workbook
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import Document, TranslationComparison, TranslationVariant
from ...services.concurrency import bind_version_token, ensure_version_token_matches
from ...services.bleu_metrics import (
    compute_bleu,
    compute_chrf,
    compute_corpus_bleu,
    compute_corpus_chrf,
)
from ...services.model_registry import (
    MODEL_SCOPE_TRANSLATION,
    get_model_entries,
    get_model_entry,
    get_model_choices,
    get_prompt_choices,
)
from ...services.translation_provider import TranslationProviderError, supports_auto_translation, translate_document_text
from .forms import TranslationCompareForm, TranslationVariantForm

translations_bp = Blueprint("translations", __name__, template_folder="templates")

TRANSLATION_CORPUS_EXPORT_HEADERS = [
    "Porownywany",
    "Liczba dokumentow",
    "BLEU korpusowe",
    "chrF++ korpusowe",
]


def _configure_model_choices(form: TranslationVariantForm, current_value: str | None = None) -> None:
    choices = get_model_choices(
        MODEL_SCOPE_TRANSLATION,
        current_value=current_value,
        include_empty=True,
    )
    form.source_model.choices = [choice for choice in choices if choice[0] != "Manualnie"]
    if not form.is_submitted():
        form.source_model.data = (current_value or "").strip()


def _configure_prompt_choices(form: TranslationVariantForm, current_value: str | None = None) -> None:
    form.source_prompt.choices = get_prompt_choices(current_value=current_value)
    if not form.is_submitted():
        form.source_prompt.data = (current_value or "").strip()


def _variant_label(variant: TranslationVariant) -> str:
    summary = variant.source_summary_with_note or variant.source_summary
    if summary:
        return f"{summary} ({variant.variant_type})"
    return variant.variant_type


def _comparison_group_key(comparison: TranslationComparison) -> tuple[str, str, str, str]:
    return (
        comparison.reference_variant.variant_type or "",
        (comparison.reference_variant.source_summary or "").strip(),
        comparison.candidate_variant.variant_type or "",
        (comparison.candidate_variant.source_summary or "").strip(),
    )


def _build_translation_corpus_report_groups() -> list[dict]:
    comparisons = (
        TranslationComparison.query.options(
            joinedload(TranslationComparison.reference_variant),
            joinedload(TranslationComparison.candidate_variant),
            joinedload(TranslationComparison.document),
        )
        .order_by(TranslationComparison.id.asc())
        .all()
    )

    grouped_comparisons: dict[tuple[str, str, str, str], list[TranslationComparison]] = defaultdict(list)
    for comparison in comparisons:
        if comparison.reference_variant is None or comparison.candidate_variant is None:
            continue
        grouped_comparisons[_comparison_group_key(comparison)].append(comparison)

    groups = []
    for key, comparison_group in grouped_comparisons.items():
        first_comparison = comparison_group[0]
        references = [comparison.reference_variant.content for comparison in comparison_group]
        candidates = [comparison.candidate_variant.content for comparison in comparison_group]
        groups.append(
            {
                "key": key,
                "reference_variant_type": key[0],
                "reference_source_model": key[1],
                "candidate_variant_type": key[2],
                "candidate_source_model": key[3],
                "reference_label": _variant_label(first_comparison.reference_variant),
                "candidate_label": _variant_label(first_comparison.candidate_variant),
                "comparison_count": len(comparison_group),
                "document_count": len({comparison.document_id for comparison in comparison_group}),
                "bleu": compute_corpus_bleu(references, candidates),
                "chrf": compute_corpus_chrf(references, candidates),
                "comparisons": comparison_group,
            }
        )

    groups.sort(
        key=lambda group: (
            group["reference_label"].lower(),
            group["candidate_label"].lower(),
            -group["comparison_count"],
        )
    )
    return groups


def _iter_translation_corpus_export_rows(groups: list[dict]) -> list[list]:
    rows: list[list] = []
    for group in groups:
        rows.append(
            [
                group["candidate_label"],
                group["document_count"],
                round(group["bleu"] or 0, 4),
                round(group["chrf"] or 0, 4),
            ]
        )
    return rows


def _invalidate_variant_comparisons(variant: TranslationVariant) -> None:
    seen_comparison_ids: set[int] = set()
    for comparison in variant.reference_comparisons.all() + variant.candidate_comparisons.all():
        if comparison.id in seen_comparison_ids:
            continue
        comparison.bleu = None
        comparison.chrf = None
        seen_comparison_ids.add(comparison.id)


def _translation_model_metadata() -> dict[str, dict[str, str | bool | None]]:
    metadata: dict[str, dict[str, str | bool | None]] = {}
    for entry in get_model_entries(MODEL_SCOPE_TRANSLATION):
        metadata[entry.name] = {
            "api_definition": (entry.api_definition or "").strip() or None,
            "model_code": (entry.model_code or "").strip() or None,
            "supports_auto_translation": supports_auto_translation(entry),
        }
    return metadata


def _selected_model_metadata(selected_name: str | None) -> dict[str, str | bool | None]:
    metadata = _translation_model_metadata()
    return metadata.get((selected_name or "").strip(), {"api_definition": None, "model_code": None, "supports_auto_translation": False})


def _model_uses_prompt(model_name: str | None) -> bool:
    selected_model = get_model_entry(MODEL_SCOPE_TRANSLATION, model_name)
    if selected_model is None:
        return False
    api_definition = (selected_model.api_definition or "").strip()
    return api_definition in {"gemini-api", "openai-api"}


def _normalize_variant_form(form: TranslationVariantForm) -> None:
    form.variant_type.data = (form.variant_type.data or "").strip() or "reference"
    source_model = (form.source_model.data or "").strip()
    if form.variant_type.data == "reference":
        source_model = ""
    form.source_model.data = source_model
    form.source_prompt.data = (form.source_prompt.data or "").strip()
    form.auto_source_tool.data = (form.auto_source_tool.data or "").strip()
    form.label.data = (form.label.data or "").strip()
    form.content.data = form.content.data or ""
    if form.variant_type.data == "reference" or not _model_uses_prompt(form.source_model.data):
        form.source_prompt.data = ""
    if form.variant_type.data == "reference":
        form.auto_source_tool.data = ""


def _resolved_source_tool(form: TranslationVariantForm) -> str | None:
    if form.variant_type.data == "reference":
        return None
    selected_model = get_model_entry(MODEL_SCOPE_TRANSLATION, form.source_model.data)
    if selected_model is None or not supports_auto_translation(selected_model):
        return None
    source_tool = (form.auto_source_tool.data or "").strip()
    return source_tool or None

@translations_bp.route("/document/<int:document_id>/new", methods=["GET", "POST"])
def new_variant(document_id: int):
    document = Document.query.get_or_404(document_id)
    form = TranslationVariantForm()
    _configure_model_choices(form)
    _configure_prompt_choices(form)
    cancel_url = url_for("documents.document_detail", document_id=document.id)
    if form.validate_on_submit():
        _normalize_variant_form(form)
        variant = TranslationVariant(
            document=document,
            variant_type=form.variant_type.data,
            source_tool=_resolved_source_tool(form),
            source_model=(form.source_model.data or "").strip() or None,
            source_prompt=(form.source_prompt.data or "").strip() or None,
            label=form.label.data,
            content=form.content.data,
        )
        db.session.add(variant)
        db.session.commit()
        flash("Dodano wariant tłumaczenia.", "success")
        return redirect(url_for("documents.document_detail", document_id=document.id))
    return render_template(
        "translations/form.html",
        form=form,
        document=document,
        translation_model_metadata=_translation_model_metadata(),
        selected_model_metadata=_selected_model_metadata(form.source_model.data),
        title="Nowy wariant tłumaczenia",
        cancel_url=cancel_url,
    )


@translations_bp.route("/variants/<int:variant_id>/edit", methods=["GET", "POST"])
def edit_variant(variant_id: int):
    variant = TranslationVariant.query.get_or_404(variant_id)
    form = TranslationVariantForm(obj=variant)
    _configure_model_choices(form, current_value=variant.source_model)
    _configure_prompt_choices(form, current_value=variant.source_prompt)
    cancel_url = url_for("documents.document_detail", document_id=variant.document_id)
    if request.method == "GET":
        bind_version_token(form, variant)
        form.auto_source_tool.data = (variant.source_tool or "").strip()
    if form.validate_on_submit():
        ensure_version_token_matches(form, variant)
        _normalize_variant_form(form)
        form.populate_obj(variant)
        variant.source_tool = _resolved_source_tool(form)
        variant.source_model = (form.source_model.data or "").strip() or None
        variant.source_prompt = (form.source_prompt.data or "").strip() or None
        _invalidate_variant_comparisons(variant)
        db.session.commit()
        flash("Zapisano wariant tłumaczenia.", "success")
        return redirect(url_for("documents.document_detail", document_id=variant.document_id))
    return render_template(
        "translations/form.html",
        form=form,
        document=variant.document,
        translation_model_metadata=_translation_model_metadata(),
        selected_model_metadata=_selected_model_metadata(form.source_model.data),
        title="Edycja wariantu tłumaczenia",
        cancel_url=cancel_url,
    )


@translations_bp.route("/document/<int:document_id>/auto-translate", methods=["POST"])
def auto_translate_document(document_id: int):
    document = Document.query.get_or_404(document_id)
    form = TranslationVariantForm()
    _configure_model_choices(form)
    _configure_prompt_choices(form)
    try:
        validate_csrf(form.csrf_token.data)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    selected_model = get_model_entry(MODEL_SCOPE_TRANSLATION, form.source_model.data)
    if selected_model is None:
        return jsonify({"error": "Wybrany model tłumaczenia nie istnieje."}), 400
    if not supports_auto_translation(selected_model):
        return jsonify({"error": "Wybrany model nie obsługuje automatycznego tłumaczenia."}), 400

    try:
        result = translate_document_text(
            model=selected_model,
            source_text=document.original_text or "",
            prompt_name=form.source_prompt.data,
        )
    except TranslationProviderError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Automatic translation failed for document_id=%s", document_id)
        return jsonify({"error": "Wystąpił nieoczekiwany błąd podczas tłumaczenia."}), 500

    return jsonify(
        {
            "content": result.text,
            "source_tool": result.source_tool,
            "source_model": selected_model.name,
            "api_definition": selected_model.api_definition,
            "model_code": selected_model.model_code,
        }
    )


@translations_bp.route("/variants/<int:variant_id>/delete", methods=["POST"])
def delete_variant(variant_id: int):
    variant = TranslationVariant.query.get_or_404(variant_id)
    document_id = variant.document_id
    db.session.delete(variant)
    db.session.commit()
    flash("Usunięto wariant tłumaczenia.", "success")
    return redirect(url_for("documents.document_detail", document_id=document_id))


@translations_bp.route("/document/<int:document_id>/compare", methods=["GET", "POST"])
def compare_variants(document_id: int):
    document = Document.query.get_or_404(document_id)
    variants = document.translation_variants.order_by(TranslationVariant.created_at.desc()).all()
    cancel_url = url_for("documents.document_detail", document_id=document.id)
    if len(variants) < 2:
        flash("Potrzebne są co najmniej dwa warianty tłumaczenia.", "warning")
        return redirect(url_for("documents.document_detail", document_id=document.id))

    form = TranslationCompareForm()
    choices = [(v.id, v.selection_display) for v in variants]
    form.reference_variant_id.choices = choices
    form.candidate_variant_id.choices = choices

    if form.validate_on_submit():
        reference = TranslationVariant.query.get_or_404(form.reference_variant_id.data)
        candidate = TranslationVariant.query.get_or_404(form.candidate_variant_id.data)
        comparison = TranslationComparison(
            document=document,
            reference_variant=reference,
            candidate_variant=candidate,
            bleu=compute_bleu(reference.content, candidate.content),
            chrf=compute_chrf(reference.content, candidate.content),
            notes=form.notes.data,
        )
        db.session.add(comparison)
        db.session.commit()
        flash("Zapisano porównanie tłumaczeń.", "success")
        return redirect(url_for("translations.view_comparison", comparison_id=comparison.id))

    return render_template("translations/compare.html", form=form, document=document, cancel_url=cancel_url)


@translations_bp.route("/comparisons/<int:comparison_id>")
def view_comparison(comparison_id: int):
    comparison = TranslationComparison.query.get_or_404(comparison_id)
    if comparison.chrf is None:
        comparison.chrf = compute_chrf(comparison.reference_variant.content, comparison.candidate_variant.content)
        db.session.commit()
    back_url = request.args.get("next") or url_for("documents.document_detail", document_id=comparison.document_id)
    return render_template(
        "translations/comparison_detail.html",
        comparison=comparison,
        back_url=back_url,
    )


@translations_bp.route("/comparisons/<int:comparison_id>/delete", methods=["POST"])
def delete_comparison(comparison_id: int):
    comparison = TranslationComparison.query.get_or_404(comparison_id)
    document_id = comparison.document_id
    db.session.delete(comparison)
    db.session.commit()
    flash("Usunięto porównanie tłumaczeń.", "success")
    return redirect(request.form.get("next") or url_for("documents.document_detail", document_id=document_id))


@translations_bp.route("/corpus-report")
def corpus_report():
    groups = _build_translation_corpus_report_groups()

    selected_key = (
        request.args.get("reference_variant_type", ""),
        request.args.get("reference_source_model", "").strip(),
        request.args.get("candidate_variant_type", ""),
        request.args.get("candidate_source_model", "").strip(),
    )

    selected_group = None
    if groups and any(selected_key):
        selected_group = next((group for group in groups if group["key"] == selected_key), None)

    return render_template(
        "translations/corpus_report.html",
        groups=groups,
        selected_group=selected_group,
    )


@translations_bp.route("/corpus-report/export/<string:file_format>")
def export_corpus_report(file_format: str):
    groups = _build_translation_corpus_report_groups()
    rows = _iter_translation_corpus_export_rows(groups)

    if file_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(TRANSLATION_CORPUS_EXPORT_HEADERS)
        writer.writerows(rows)
        data = io.BytesIO(buffer.getvalue().encode("utf-8-sig"))
        data.seek(0)
        return send_file(
            data,
            as_attachment=True,
            download_name="raport_tlumaczen.csv",
            mimetype="text/csv",
        )

    if file_format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Raport tlumaczen"
        sheet.append(TRANSLATION_CORPUS_EXPORT_HEADERS)
        for row in rows:
            sheet.append(row)
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="raport_tlumaczen.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    flash("Nieobsługiwany format eksportu raportu tłumaczeń.", "warning")
    return redirect(url_for("translations.corpus_report"))
