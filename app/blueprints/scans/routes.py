import io
import string
import zipfile
from pathlib import Path
from unicodedata import normalize

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, send_from_directory, url_for

from ...extensions import db
from ...models import HTRComparison, Scan, ScanText
from ...services.concurrency import bind_version_token, ensure_version_token_matches
from ..htr.forms import GROUND_TRUTH_TEXT_TYPES
from ...services.file_storage import save_scan_image
from .forms import BulkScanImportForm, MAX_BULK_IMPORT_FILES, ScanForm, ScanTrainingExportForm

scans_bp = Blueprint("scans", __name__, template_folder="templates")


def _original_scan_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    prefix, separator, rest = filename.partition("_")
    if separator and len(prefix) == 32 and all(char in string.hexdigits for char in prefix):
        return rest
    return filename


def _unique_archive_name(name: str, used_names: set[str]) -> str:
    candidate = name
    stem = Path(name).stem
    suffix = Path(name).suffix
    counter = 2
    while candidate in used_names:
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    used_names.add(candidate)
    return candidate


def _scan_title_from_filename(filename: str | None) -> str:
    if not filename:
        return "Nowy skan"
    stem = Path(filename).stem
    cleaned = normalize("NFKC", stem).replace("_", " ").replace("-", " ").strip()
    return " ".join(cleaned.split()) or stem or "Nowy skan"


def _training_export_candidates() -> list[tuple[Scan, ScanText]]:
    candidates: list[tuple[Scan, ScanText]] = []
    scans = Scan.query.filter_by(is_training_sample=True).order_by(Scan.id.asc()).all()
    for scan in scans:
        if not scan.image_path:
            continue
        primary_ground_truth = (
            scan.texts.filter(
                ScanText.main_ground_truth.is_(True),
                ScanText.text_type.in_(tuple(GROUND_TRUTH_TEXT_TYPES)),
            )
            .order_by(ScanText.id.asc())
            .first()
        )
        if primary_ground_truth is not None:
            candidates.append((scan, primary_ground_truth))
    return candidates

SCAN_SORT_FIELDS = {
    "id": lambda direction: (Scan.id.asc(),) if direction == "asc" else (Scan.id.desc(),),
    "title": lambda direction: (
        (Scan.title.asc(), Scan.id.asc()) if direction == "asc" else (Scan.title.desc(), Scan.id.asc())
    ),
    "shelfmark": lambda direction: (
        (Scan.shelfmark.asc().nullslast(), Scan.id.asc())
        if direction == "asc"
        else (Scan.shelfmark.desc().nullslast(), Scan.id.asc())
    ),
    "folio": lambda direction: (
        (Scan.folio.asc().nullslast(), Scan.id.asc())
        if direction == "asc"
        else (Scan.folio.desc().nullslast(), Scan.id.asc())
    ),
    "hand": lambda direction: (
        (Scan.hand.asc().nullslast(), Scan.id.asc())
        if direction == "asc"
        else (Scan.hand.desc().nullslast(), Scan.id.asc())
    ),
    "sequence_no": lambda direction: (
        (Scan.sequence_no.asc().nullslast(), Scan.id.asc())
        if direction == "asc"
        else (Scan.sequence_no.desc().nullslast(), Scan.id.asc())
    ),
}

HTR_COMPARISON_SORT_FIELDS = {
    "id": lambda direction: (HTRComparison.id.asc(),) if direction == "asc" else (HTRComparison.id.desc(),),
    "cer": lambda direction: (
        (HTRComparison.cer.asc().nullslast(), HTRComparison.id.asc())
        if direction == "asc"
        else (HTRComparison.cer.desc().nullslast(), HTRComparison.id.asc())
    ),
    "wer": lambda direction: (
        (HTRComparison.wer.asc().nullslast(), HTRComparison.id.asc())
        if direction == "asc"
        else (HTRComparison.wer.desc().nullslast(), HTRComparison.id.asc())
    ),
}

SCAN_TEXT_SORT_FIELDS = {
    "id": lambda direction: (ScanText.id.asc(),) if direction == "asc" else (ScanText.id.desc(),),
    "text_type": lambda direction: (
        (ScanText.text_type.asc(), ScanText.id.asc())
        if direction == "asc"
        else (ScanText.text_type.desc(), ScanText.id.asc())
    ),
    "label": lambda direction: (
        (ScanText.label.asc().nullslast(), ScanText.id.asc())
        if direction == "asc"
        else (ScanText.label.desc().nullslast(), ScanText.id.asc())
    ),
    "source": lambda direction: (
        (
            db.func.coalesce(
                db.func.nullif(ScanText.source_model, ""),
                db.func.nullif(ScanText.source_tool, ""),
            ).asc().nullslast(),
            ScanText.id.asc(),
        )
        if direction == "asc"
        else (
            db.func.coalesce(
                db.func.nullif(ScanText.source_model, ""),
                db.func.nullif(ScanText.source_tool, ""),
            ).desc().nullslast(),
            ScanText.id.asc(),
        )
    ),
}

@scans_bp.route("/")
def list_scans():
    q = request.args.get("q", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    if sort_by not in SCAN_SORT_FIELDS:
        sort_by = "id"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"
    query = Scan.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Scan.title.ilike(like),
                Scan.shelfmark.ilike(like),
                Scan.folio.ilike(like),
                Scan.hand.ilike(like),
            )
        )
    scans = query.order_by(*SCAN_SORT_FIELDS[sort_by](sort_dir)).all()
    return render_template("scans/list.html", scans=scans, q=q, sort_by=sort_by, sort_dir=sort_dir)


@scans_bp.route("/export-training-sample", methods=["GET", "POST"])
def export_training_sample():
    form = ScanTrainingExportForm()
    candidates = _training_export_candidates()
    cancel_url = url_for("scans.list_scans")

    if form.validate_on_submit():
        if not candidates:
            flash(
                "Brak skanów kwalifikujących się do eksportu próbki uczącej.",
                "warning",
            )
            return redirect(url_for("scans.list_scans"))

        archive_buffer = io.BytesIO()
        used_names: set[str] = set()
        upload_dir = Path(current_app.config["UPLOAD_FOLDER"])

        with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for scan, text in candidates:
                original_image_name = _original_scan_filename(scan.image_path) or f"scan_{scan.id}"
                text_name = _unique_archive_name(f"{Path(original_image_name).stem}.txt", used_names)
                archive.writestr(text_name, text.content or "")

                if form.include_images.data:
                    image_path = upload_dir / scan.image_path
                    if image_path.exists():
                        image_name = _unique_archive_name(original_image_name, used_names)
                        archive.write(image_path, arcname=image_name)

        archive_buffer.seek(0)
        return send_file(
            archive_buffer,
            as_attachment=True,
            download_name="probka_uczaca.zip",
            mimetype="application/zip",
        )

    return render_template(
        "scans/export_training_sample.html",
        form=form,
        candidate_count=len(candidates),
        cancel_url=cancel_url,
    )


@scans_bp.route("/new", methods=["GET", "POST"])
def new_scan():
    form = ScanForm()
    cancel_url = url_for("scans.list_scans")
    if form.validate_on_submit():
        scan = Scan(
            title=form.title.data,
            shelfmark=form.shelfmark.data,
            folio=form.folio.data,
            sequence_no=form.sequence_no.data,
            hand=form.hand.data,
            notes=form.notes.data,
            is_training_sample=form.is_training_sample.data,
            is_done=form.is_done.data,
        )
        if form.image_file.data:
            try:
                stored = save_scan_image(form.image_file.data, current_app.config["UPLOAD_FOLDER"])
                scan.image_path = stored["image_path"]
                scan.image_width = stored["image_width"]
                scan.image_height = stored["image_height"]
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("scans/form.html", form=form, title="Nowy skan", cancel_url=cancel_url, scan=None)

        db.session.add(scan)
        db.session.commit()
        flash("Dodano skan.", "success")
        return redirect(url_for("scans.scan_detail", scan_id=scan.id))
    return render_template("scans/form.html", form=form, title="Nowy skan", cancel_url=cancel_url, scan=None)


@scans_bp.route("/bulk-import", methods=["GET", "POST"])
def bulk_import_scans():
    form = BulkScanImportForm()
    cancel_url = url_for("scans.list_scans")
    if form.validate_on_submit():
        files = [file for file in form.image_files.data if file and file.filename]
        imported_count = 0

        try:
            for file in files:
                stored = save_scan_image(file, current_app.config["UPLOAD_FOLDER"])
                scan = Scan(
                    title=_scan_title_from_filename(file.filename),
                    shelfmark=form.shelfmark.data,
                    hand=form.hand.data,
                    notes=form.notes.data,
                    is_training_sample=form.is_training_sample.data,
                    image_path=stored["image_path"],
                    image_width=stored["image_width"],
                    image_height=stored["image_height"],
                )
                db.session.add(scan)
                imported_count += 1

            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template(
                "scans/bulk_import.html",
                form=form,
                cancel_url=cancel_url,
                max_files=MAX_BULK_IMPORT_FILES,
            )

        flash(
            f"Dodano {imported_count} {'skan' if imported_count == 1 else 'skany' if 2 <= imported_count <= 4 else 'skanów'}.",
            "success",
        )
        return redirect(url_for("scans.list_scans"))

    return render_template(
        "scans/bulk_import.html",
        form=form,
        cancel_url=cancel_url,
        max_files=MAX_BULK_IMPORT_FILES,
    )


@scans_bp.route("/<int:scan_id>")
def scan_detail(scan_id: int):
    scan = Scan.query.get_or_404(scan_id)
    text_sort_by = request.args.get("text_sort_by", "id")
    text_sort_dir = request.args.get("text_sort_dir", "asc")
    comparison_sort_by = request.args.get("comparison_sort_by", "id")
    comparison_sort_dir = request.args.get("comparison_sort_dir", "asc")
    if text_sort_by not in SCAN_TEXT_SORT_FIELDS:
        text_sort_by = "id"
    if text_sort_dir not in {"asc", "desc"}:
        text_sort_dir = "asc"
    if comparison_sort_by not in HTR_COMPARISON_SORT_FIELDS:
        comparison_sort_by = "id"
    if comparison_sort_dir not in {"asc", "desc"}:
        comparison_sort_dir = "asc"
    texts = scan.texts.order_by(*SCAN_TEXT_SORT_FIELDS[text_sort_by](text_sort_dir)).all()
    comparisons = scan.comparisons.order_by(*HTR_COMPARISON_SORT_FIELDS[comparison_sort_by](comparison_sort_dir)).all()
    return render_template(
        "scans/detail.html",
        scan=scan,
        texts=texts,
        comparisons=comparisons,
        text_sort_by=text_sort_by,
        text_sort_dir=text_sort_dir,
        comparison_sort_by=comparison_sort_by,
        comparison_sort_dir=comparison_sort_dir,
    )


@scans_bp.route("/<int:scan_id>/edit", methods=["GET", "POST"])
def edit_scan(scan_id: int):
    scan = Scan.query.get_or_404(scan_id)
    form = ScanForm(obj=scan)
    cancel_url = request.args.get("next") or url_for("scans.scan_detail", scan_id=scan.id)
    if request.method == "GET":
        bind_version_token(form, scan)
    if form.validate_on_submit():
        ensure_version_token_matches(form, scan)
        form.populate_obj(scan)
        if form.image_file.data:
            try:
                stored = save_scan_image(form.image_file.data, current_app.config["UPLOAD_FOLDER"])
                scan.image_path = stored["image_path"]
                scan.image_width = stored["image_width"]
                scan.image_height = stored["image_height"]
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("scans/form.html", form=form, title="Edycja metadanych skanu", cancel_url=cancel_url, scan=scan)
        db.session.commit()
        flash("Zapisano zmiany skanu.", "success")
        return redirect(url_for("scans.scan_detail", scan_id=scan.id))
    return render_template("scans/form.html", form=form, title="Edycja metadanych skanu", cancel_url=cancel_url, scan=scan)


@scans_bp.route("/<int:scan_id>/delete", methods=["POST"])
def delete_scan(scan_id: int):
    scan = Scan.query.get_or_404(scan_id)
    db.session.delete(scan)
    db.session.commit()
    flash("Usunięto skan.", "success")
    return redirect(url_for("scans.list_scans"))


@scans_bp.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    return send_from_directory(upload_dir, filename)
