from collections import defaultdict

from flask import Blueprint, flash, redirect, render_template, request, url_for
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
from ...services.model_registry import MANUAL_MODEL_NAME, MODEL_SCOPE_TRANSLATION, get_model_choices
from .forms import TranslationCompareForm, TranslationVariantForm

translations_bp = Blueprint("translations", __name__, template_folder="templates")


def _configure_model_choices(form: TranslationVariantForm, current_value: str | None = None) -> None:
    form.source_model.choices = get_model_choices(MODEL_SCOPE_TRANSLATION, current_value=current_value)
    if not form.is_submitted():
        form.source_model.data = (current_value or "").strip() or MANUAL_MODEL_NAME


def _variant_label(variant: TranslationVariant) -> str:
    if variant.source_display:
        return f"{variant.source_display} ({variant.variant_type})"
    return variant.variant_type


def _comparison_group_key(comparison: TranslationComparison) -> tuple[str, str, str, str]:
    return (
        comparison.reference_variant.variant_type or "",
        (comparison.reference_variant.source_display or "").strip(),
        comparison.candidate_variant.variant_type or "",
        (comparison.candidate_variant.source_display or "").strip(),
    )


def _invalidate_variant_comparisons(variant: TranslationVariant) -> None:
    seen_comparison_ids: set[int] = set()
    for comparison in variant.reference_comparisons.all() + variant.candidate_comparisons.all():
        if comparison.id in seen_comparison_ids:
            continue
        comparison.bleu = None
        comparison.chrf = None
        seen_comparison_ids.add(comparison.id)

@translations_bp.route("/document/<int:document_id>/new", methods=["GET", "POST"])
def new_variant(document_id: int):
    document = Document.query.get_or_404(document_id)
    form = TranslationVariantForm()
    _configure_model_choices(form)
    cancel_url = url_for("documents.document_detail", document_id=document.id)
    if form.validate_on_submit():
        variant = TranslationVariant(
            document=document,
            variant_type=form.variant_type.data,
            source_model=(form.source_model.data or "").strip() or None,
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
        title="Nowy wariant tłumaczenia",
        cancel_url=cancel_url,
    )


@translations_bp.route("/variants/<int:variant_id>/edit", methods=["GET", "POST"])
def edit_variant(variant_id: int):
    variant = TranslationVariant.query.get_or_404(variant_id)
    form = TranslationVariantForm(obj=variant)
    _configure_model_choices(form, current_value=variant.source_display)
    cancel_url = url_for("documents.document_detail", document_id=variant.document_id)
    if request.method == "GET":
        bind_version_token(form, variant)
    if form.validate_on_submit():
        ensure_version_token_matches(form, variant)
        form.populate_obj(variant)
        variant.source_tool = None
        variant.source_model = (form.source_model.data or "").strip() or None
        _invalidate_variant_comparisons(variant)
        db.session.commit()
        flash("Zapisano wariant tłumaczenia.", "success")
        return redirect(url_for("documents.document_detail", document_id=variant.document_id))
    return render_template(
        "translations/form.html",
        form=form,
        document=variant.document,
        title="Edycja wariantu tłumaczenia",
        cancel_url=cancel_url,
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
    choices = [(v.id, f"{v.source_display or v.variant_type} | {v.variant_type}") for v in variants]
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
    return render_template("translations/comparison_detail.html", comparison=comparison)


@translations_bp.route("/corpus-report")
def corpus_report():
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
