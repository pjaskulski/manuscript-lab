import csv
import io
import re
from collections import defaultdict
from pathlib import Path

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import HTRComparison, Scan, ScanText
from ...services.concurrency import bind_version_token, ensure_version_token_matches
from ...services.gemini_alignment import GeminiAlignmentError, align_transcription_lines
from ...services.htr_metrics import compute_corpus_htr_metrics, compute_htr_metrics, make_html_diff
from ...services.model_registry import MANUAL_MODEL_NAME, MODEL_SCOPE_HTR, get_model_choices
from ...services.text_normalization import normalize_text
from .forms import GROUND_TRUTH_TEXT_TYPES, HTRCompareForm, ScanTextForm, ScanTextWorkspaceForm

htr_bp = Blueprint("htr", __name__, template_folder="templates")

HTR_CORPUS_EXPORT_HEADERS = ["Model", "Normalizacja", "Liczba Skanow", "CER", "WER"]


def _configure_model_choices(form: ScanTextForm, current_value: str | None = None) -> None:
    form.source_model.choices = get_model_choices(MODEL_SCOPE_HTR, current_value=current_value)
    if not form.is_submitted():
        form.source_model.data = (current_value or "").strip() or MANUAL_MODEL_NAME


def _is_ground_truth_type(text_type: str | None) -> bool:
    return (text_type or "").strip() in GROUND_TRUTH_TEXT_TYPES


def _text_label(text: ScanText) -> str:
    return text.comparison_display


def _normalize_alignment_check_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _comparison_group_key(comparison: HTRComparison) -> tuple[str, str, str, str, str]:
    return (
        comparison.reference_text.text_type or "",
        (comparison.reference_text.source_display or "").strip(),
        comparison.candidate_text.text_type or "",
        (comparison.candidate_text.source_display or "").strip(),
        (comparison.normalization_profile or "").strip(),
    )


def _build_corpus_report_groups() -> list[dict]:
    comparisons = (
        HTRComparison.query.options(
            joinedload(HTRComparison.reference_text),
            joinedload(HTRComparison.candidate_text),
            joinedload(HTRComparison.scan),
        )
        .order_by(HTRComparison.id.asc())
        .all()
    )

    grouped_comparisons: dict[tuple[str, str, str, str, str], list[HTRComparison]] = defaultdict(list)
    for comparison in comparisons:
        if comparison.reference_text is None or comparison.candidate_text is None:
            continue
        grouped_comparisons[_comparison_group_key(comparison)].append(comparison)

    groups = []
    for key, comparison_group in grouped_comparisons.items():
        first_comparison = comparison_group[0]
        profile = key[4] or "lowercase"
        references = [comparison.reference_text.content for comparison in comparison_group]
        candidates = [comparison.candidate_text.content for comparison in comparison_group]
        corpus_metrics = compute_corpus_htr_metrics(references, candidates, profile=profile)
        groups.append(
            {
                "key": key,
                "reference_text_type": key[0],
                "reference_source_model": key[1],
                "candidate_text_type": key[2],
                "candidate_source_model": key[3],
                "normalization_profile": key[4],
                "reference_label": _text_label(first_comparison.reference_text),
                "candidate_label": _text_label(first_comparison.candidate_text),
                "comparison_count": len(comparison_group),
                "scan_count": len({comparison.scan_id for comparison in comparison_group}),
                "cer": corpus_metrics["cer"],
                "wer": corpus_metrics["wer"],
                "comparisons": comparison_group,
            }
        )

    groups.sort(
        key=lambda group: (
            group["reference_label"].lower(),
            group["candidate_label"].lower(),
            group["normalization_profile"].lower(),
            -group["comparison_count"],
        )
    )
    return groups


def _iter_corpus_export_rows(groups: list[dict]) -> list[list]:
    rows: list[list] = []
    for group in groups:
        rows.append(
            [
                group["candidate_label"],
                group["normalization_profile"] or "-",
                group["scan_count"],
                round((group["cer"] or 0) * 100, 2),
                round((group["wer"] or 0) * 100, 2),
            ]
        )
    return rows


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
    if request.method == "GET":
        bind_version_token(form, text)
    if form.validate_on_submit():
        ensure_version_token_matches(form, text)
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
    if request.method == "GET":
        bind_version_token(form, text)
    if form.validate_on_submit():
        ensure_version_token_matches(form, text)
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


@htr_bp.route("/texts/<int:text_id>/align-lines", methods=["POST"])
def align_scan_text_lines(text_id: int):
    text = ScanText.query.get_or_404(text_id)
    if not text.scan.image_path:
        return jsonify({"error": "Ten skan nie ma przypisanego obrazu."}), 400

    payload = request.get_json(silent=True) or {}
    raw_text = (payload.get("text") or "").strip()
    if not raw_text:
        return jsonify({"error": "Brak tekstu do dopasowania."}), 400

    image_path = Path(current_app.config["UPLOAD_FOLDER"]) / text.scan.image_path
    try:
        formatted_text = align_transcription_lines(
            api_key=current_app.config.get("GEMINI_API_KEY"),
            model=current_app.config.get("GEMINI_ALIGNMENT_MODEL", "gemini-3-flash-preview"),
            image_path=image_path,
            raw_text=raw_text,
        )
    except GeminiAlignmentError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Gemini alignment failed for scan text %s", text_id)
        return jsonify({"error": "Nie udalo sie przetworzyc tekstu przez Gemini."}), 500

    normalized_original = _normalize_alignment_check_text(raw_text)
    normalized_formatted = _normalize_alignment_check_text(formatted_text)
    exact_match = normalized_formatted == normalized_original
    contained_match = bool(normalized_formatted) and normalized_formatted in normalized_original

    return jsonify(
        {
            "formatted_text": formatted_text,
            "validation": {
                "exact_match": exact_match,
                "contained_match": contained_match,
                "accepted": exact_match or contained_match,
                "normalized_original_length": len(normalized_original),
                "normalized_formatted_length": len(normalized_formatted),
            },
        }
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
    back_url = request.args.get("next", "").strip() or url_for("scans.scan_detail", scan_id=comparison.scan.id)
    back_label = "Wróć do raportu" if "/corpus-report" in back_url else "Wróć do skanu"
    diff_html = make_html_diff(
        normalize_text(comparison.reference_text.content, profile=comparison.normalization_profile or "lowercase"),
        normalize_text(comparison.candidate_text.content, profile=comparison.normalization_profile or "lowercase"),
    )
    return render_template(
        "htr/comparison_detail.html",
        comparison=comparison,
        diff_html=diff_html,
        back_url=back_url,
        back_label=back_label,
    )


@htr_bp.route("/corpus-report")
def corpus_report():
    groups = _build_corpus_report_groups()

    selected_key = (
        request.args.get("reference_text_type", ""),
        request.args.get("reference_source_model", "").strip(),
        request.args.get("candidate_text_type", ""),
        request.args.get("candidate_source_model", "").strip(),
        request.args.get("normalization_profile", "").strip(),
    )

    selected_group = None
    if groups and any(selected_key):
        selected_group = next((group for group in groups if group["key"] == selected_key), None)

    return render_template(
        "htr/corpus_report.html",
        groups=groups,
        selected_group=selected_group,
    )


@htr_bp.route("/corpus-report/export/<string:file_format>")
def export_corpus_report(file_format: str):
    groups = _build_corpus_report_groups()
    rows = _iter_corpus_export_rows(groups)

    if file_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(HTR_CORPUS_EXPORT_HEADERS)
        writer.writerows(rows)
        data = io.BytesIO(buffer.getvalue().encode("utf-8-sig"))
        data.seek(0)
        return send_file(
            data,
            as_attachment=True,
            download_name="raport_htr.csv",
            mimetype="text/csv",
        )

    if file_format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Raport HTR"
        sheet.append(HTR_CORPUS_EXPORT_HEADERS)
        for row in rows:
            sheet.append(row)
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="raport_htr.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    flash("Nieobsługiwany format eksportu raportu HTR.", "warning")
    return redirect(url_for("htr.corpus_report"))


@htr_bp.route("/comparisons/<int:comparison_id>/delete", methods=["POST"])
def delete_comparison(comparison_id: int):
    comparison = HTRComparison.query.get_or_404(comparison_id)
    scan_id = comparison.scan_id
    db.session.delete(comparison)
    db.session.commit()
    flash("Usunięto porównanie HTR.", "success")
    return redirect(request.form.get("next") or url_for("scans.scan_detail", scan_id=scan_id))
