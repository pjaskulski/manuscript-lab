from flask import Blueprint, flash, redirect, render_template, url_for

from ...extensions import db
from ...models import HTRComparison, Scan, ScanText
from ...services.htr_metrics import compute_htr_metrics, make_html_diff
from ...services.model_registry import MANUAL_MODEL_NAME, MODEL_SCOPE_HTR, get_model_choices
from ...services.text_normalization import normalize_text
from .forms import GROUND_TRUTH_TEXT_TYPES, HTRCompareForm, ScanTextForm, ScanTextWorkspaceForm

htr_bp = Blueprint("htr", __name__, template_folder="templates")


def _configure_model_choices(form: ScanTextForm, current_value: str | None = None) -> None:
    form.source_model.choices = get_model_choices(MODEL_SCOPE_HTR, current_value=current_value)
    if not form.is_submitted():
        form.source_model.data = (current_value or "").strip() or MANUAL_MODEL_NAME


def _is_ground_truth_type(text_type: str | None) -> bool:
    return (text_type or "").strip() in GROUND_TRUTH_TEXT_TYPES


def _sync_main_ground_truth(text: ScanText) -> None:
    if not _is_ground_truth_type(text.text_type) or not text.main_ground_truth:
        text.main_ground_truth = False
        return

    other_texts = (
        ScanText.query.filter(
            ScanText.scan_id == text.scan_id,
            ScanText.id != text.id,
            ScanText.main_ground_truth.is_(True),
        )
        .all()
    )
    for other_text in other_texts:
        other_text.main_ground_truth = False

@htr_bp.route("/scan/<int:scan_id>/texts/new", methods=["GET", "POST"])
def new_scan_text(scan_id: int):
    scan = Scan.query.get_or_404(scan_id)
    form = ScanTextForm()
    _configure_model_choices(form)
    cancel_url = url_for("scans.scan_detail", scan_id=scan.id)
    if form.validate_on_submit():
        source_model = (form.source_model.data or "").strip() or None
        text = ScanText(
            scan=scan,
            text_type=form.text_type.data,
            label=form.label.data,
            source_tool=None,
            source_model=source_model,
            main_ground_truth=form.main_ground_truth.data,
            is_line_based=form.is_line_based.data,
            content=form.content.data,
        )
        db.session.add(text)
        db.session.flush()
        _sync_main_ground_truth(text)
        db.session.commit()
        flash("Dodano wariant tekstu.", "success")
        return redirect(url_for("scans.scan_detail", scan_id=scan.id))
    return render_template(
        "htr/form.html",
        form=form,
        scan=scan,
        title="Nowy wariant tekstu",
        cancel_url=cancel_url,
        ground_truth_types=sorted(GROUND_TRUTH_TEXT_TYPES),
    )


@htr_bp.route("/texts/<int:text_id>/edit", methods=["GET", "POST"])
def edit_scan_text(text_id: int):
    text = ScanText.query.get_or_404(text_id)
    form = ScanTextForm(obj=text)
    _configure_model_choices(form, current_value=text.source_display)
    cancel_url = url_for("scans.scan_detail", scan_id=text.scan_id)
    if form.validate_on_submit():
        form.populate_obj(text)
        text.source_tool = None
        text.source_model = (form.source_model.data or "").strip() or None
        _sync_main_ground_truth(text)
        db.session.commit()
        flash("Zapisano wariant tekstu.", "success")
        return redirect(url_for("scans.scan_detail", scan_id=text.scan_id))
    return render_template(
        "htr/form.html",
        form=form,
        scan=text.scan,
        title="Edycja wariantu tekstu",
        cancel_url=cancel_url,
        ground_truth_types=sorted(GROUND_TRUTH_TEXT_TYPES),
    )


@htr_bp.route("/texts/<int:text_id>/workspace", methods=["GET", "POST"])
def workspace_scan_text(text_id: int):
    text = ScanText.query.get_or_404(text_id)
    form = ScanTextWorkspaceForm(obj=text)
    cancel_url = url_for("scans.scan_detail", scan_id=text.scan_id)
    if form.validate_on_submit():
        text.content = form.content.data
        db.session.commit()
        flash("Zapisano korekty wariantu tekstu.", "success")
        return redirect(url_for("htr.workspace_scan_text", text_id=text.id))
    return render_template(
        "htr/workspace.html",
        form=form,
        scan=text.scan,
        text=text,
        title="HTR",
        cancel_url=cancel_url,
    )


@htr_bp.route("/texts/<int:text_id>/delete", methods=["POST"])
def delete_scan_text(text_id: int):
    text = ScanText.query.get_or_404(text_id)
    scan_id = text.scan_id
    db.session.delete(text)
    db.session.commit()
    flash("Usunięto wariant tekstu.", "success")
    return redirect(url_for("scans.scan_detail", scan_id=scan_id))


@htr_bp.route("/scan/<int:scan_id>/compare", methods=["GET", "POST"])
def compare_scan_texts(scan_id: int):
    scan = Scan.query.get_or_404(scan_id)
    texts = scan.texts.order_by(ScanText.created_at.desc()).all()
    cancel_url = url_for("scans.scan_detail", scan_id=scan.id)
    if len(texts) < 2:
        flash("Potrzebne są co najmniej dwa warianty tekstu.", "warning")
        return redirect(url_for("scans.scan_detail", scan_id=scan.id))

    form = HTRCompareForm()
    form.reference_text_id.choices = [(t.id, t.comparison_display) for t in texts]
    form.candidate_text_id.choices = [(t.id, t.comparison_display) for t in texts]

    comparison = None
    if form.validate_on_submit():
        reference = ScanText.query.get_or_404(form.reference_text_id.data)
        candidate = ScanText.query.get_or_404(form.candidate_text_id.data)
        metrics = compute_htr_metrics(reference.content, candidate.content, profile=form.normalization_profile.data)
        comparison = HTRComparison(
            scan=scan,
            reference_text=reference,
            candidate_text=candidate,
            cer=metrics["cer"],
            wer=metrics["wer"],
            normalization_profile=form.normalization_profile.data,
            diff_html=make_html_diff(metrics["reference_normalized"], metrics["candidate_normalized"]),
        )
        db.session.add(comparison)
        db.session.commit()
        flash("Zapisano porównanie HTR.", "success")
        return redirect(url_for("htr.view_comparison", comparison_id=comparison.id))

    return render_template("htr/compare.html", form=form, scan=scan, comparison=comparison, cancel_url=cancel_url)


@htr_bp.route("/comparisons/<int:comparison_id>")
def view_comparison(comparison_id: int):
    comparison = HTRComparison.query.get_or_404(comparison_id)
    diff_html = make_html_diff(
        normalize_text(comparison.reference_text.content, profile=comparison.normalization_profile or "lowercase"),
        normalize_text(comparison.candidate_text.content, profile=comparison.normalization_profile or "lowercase"),
    )
    return render_template("htr/comparison_detail.html", comparison=comparison, diff_html=diff_html)


@htr_bp.route("/comparisons/<int:comparison_id>/delete", methods=["POST"])
def delete_comparison(comparison_id: int):
    comparison = HTRComparison.query.get_or_404(comparison_id)
    scan_id = comparison.scan_id
    db.session.delete(comparison)
    db.session.commit()
    flash("Usunięto porównanie HTR.", "success")
    return redirect(url_for("scans.scan_detail", scan_id=scan_id))
