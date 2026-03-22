from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import Document, DocumentScanLink, Scan, ScanText, TranslationComparison, TranslationVariant
from ...services.concurrency import (
    ConcurrentUpdateError,
    bind_version_token,
    ensure_version_token_matches,
    version_token_for,
)
from ...services.bleu_metrics import compute_bleu, compute_chrf
from ...services.document_builder import build_document_text_from_scan_texts
from .forms import DocumentForm, LinkScanForm

documents_bp = Blueprint("documents", __name__, template_folder="templates")

DOCUMENT_SORT_FIELDS = {
    "id": lambda direction: (Document.id.asc(),) if direction == "asc" else (Document.id.desc(),),
    "title": lambda direction: (
        (Document.title.asc(), Document.id.asc()) if direction == "asc" else (Document.title.desc(), Document.id.asc())
    ),
    "document_code": lambda direction: (
        (Document.document_code.asc().nullslast(), Document.id.asc())
        if direction == "asc"
        else (Document.document_code.desc().nullslast(), Document.id.asc())
    ),
}

DOCUMENT_VARIANT_SORT_FIELDS = {
    "id": lambda direction: (TranslationVariant.id.asc(),) if direction == "asc" else (TranslationVariant.id.desc(),),
    "variant_type": lambda direction: (
        (TranslationVariant.variant_type.asc(), TranslationVariant.id.asc())
        if direction == "asc"
        else (TranslationVariant.variant_type.desc(), TranslationVariant.id.asc())
    ),
    "source_model": lambda direction: (
        (TranslationVariant.source_model.asc().nullslast(), TranslationVariant.id.asc())
        if direction == "asc"
        else (TranslationVariant.source_model.desc().nullslast(), TranslationVariant.id.asc())
    ),
    "source_prompt": lambda direction: (
        (TranslationVariant.source_prompt.asc().nullslast(), TranslationVariant.id.asc())
        if direction == "asc"
        else (TranslationVariant.source_prompt.desc().nullslast(), TranslationVariant.id.asc())
    ),
    "notes": lambda direction: (
        (TranslationVariant.label.asc().nullslast(), TranslationVariant.id.asc())
        if direction == "asc"
        else (TranslationVariant.label.desc().nullslast(), TranslationVariant.id.asc())
    ),
}

DOCUMENT_COMPARISON_SORT_FIELDS = {
    "id": lambda direction: (TranslationComparison.id.asc(),) if direction == "asc" else (TranslationComparison.id.desc(),),
    "reference": lambda direction: (
        (TranslationComparison.reference_variant_id.asc(), TranslationComparison.id.asc())
        if direction == "asc"
        else (TranslationComparison.reference_variant_id.desc(), TranslationComparison.id.asc())
    ),
    "candidate": lambda direction: (
        (TranslationComparison.candidate_variant_id.asc(), TranslationComparison.id.asc())
        if direction == "asc"
        else (TranslationComparison.candidate_variant_id.desc(), TranslationComparison.id.asc())
    ),
    "bleu": lambda direction: (
        (TranslationComparison.bleu.asc().nullslast(), TranslationComparison.id.asc())
        if direction == "asc"
        else (TranslationComparison.bleu.desc().nullslast(), TranslationComparison.id.asc())
    ),
    "chrf": lambda direction: (
        (TranslationComparison.chrf.asc().nullslast(), TranslationComparison.id.asc())
        if direction == "asc"
        else (TranslationComparison.chrf.desc().nullslast(), TranslationComparison.id.asc())
    ),
}


def _filtered_documents_query(query_text: str):
    query = Document.query
    if query_text:
        like = f"%{query_text}%"
        query = query.filter(
            db.or_(
                Document.title.ilike(like),
                Document.document_code.ilike(like),
                Document.bibliographic_address.ilike(like),
            )
        )
    return query


def _document_neighbors(
    document_id: int, query_text: str, sort_by: str, sort_dir: str
) -> tuple[Document | None, Document | None]:
    document_ids = [
        current_document_id
        for current_document_id, in _filtered_documents_query(query_text)
        .with_entities(Document.id)
        .order_by(*DOCUMENT_SORT_FIELDS[sort_by](sort_dir))
        .all()
    ]
    try:
        index = document_ids.index(document_id)
    except ValueError:
        return None, None

    previous_document = Document.query.get(document_ids[index - 1]) if index > 0 else None
    next_document = Document.query.get(document_ids[index + 1]) if index < len(document_ids) - 1 else None
    return previous_document, next_document


def _primary_ground_truth_for_scan(scan_id: int) -> ScanText | None:
    return (
        ScanText.query.filter(
            ScanText.scan_id == scan_id,
            ScanText.main_ground_truth.is_(True),
            ScanText.text_type.in_(
                (
                    "ground_truth",
                    "ground_truth_diplomatic",
                    "ground_truth_expanded",
                )
            ),
        )
        .order_by(ScanText.updated_at.desc(), ScanText.id.desc())
        .first()
    )

@documents_bp.route("/")
def list_documents():
    q = request.args.get("q", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    if sort_by not in DOCUMENT_SORT_FIELDS:
        sort_by = "id"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"
    documents = _filtered_documents_query(q).order_by(*DOCUMENT_SORT_FIELDS[sort_by](sort_dir)).all()
    return render_template("documents/list.html", documents=documents, q=q, sort_by=sort_by, sort_dir=sort_dir)


@documents_bp.route("/new", methods=["GET", "POST"])
def new_document():
    form = DocumentForm()
    cancel_url = url_for("documents.list_documents")
    if form.validate_on_submit():
        document = Document(
            title=form.title.data,
            document_code=form.document_code.data or None,
            bibliographic_address=form.bibliographic_address.data or None,
            notes=form.notes.data,
            original_text=form.original_text.data,
        )
        db.session.add(document)
        db.session.commit()
        flash("Dodano dokument.", "success")
        return redirect(url_for("documents.document_detail", document_id=document.id))
    return render_template("documents/form.html", form=form, title="Nowy dokument", cancel_url=cancel_url)


@documents_bp.route("/<int:document_id>")
def document_detail(document_id: int):
    document = Document.query.get_or_404(document_id)
    q = request.args.get("q", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    variant_sort_by = request.args.get("variant_sort_by", "id")
    variant_sort_dir = request.args.get("variant_sort_dir", "asc")
    comparison_sort_by = request.args.get("comparison_sort_by", "id")
    comparison_sort_dir = request.args.get("comparison_sort_dir", "asc")

    if sort_by not in DOCUMENT_SORT_FIELDS:
        sort_by = "id"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"
    if variant_sort_by not in DOCUMENT_VARIANT_SORT_FIELDS:
        variant_sort_by = "id"
    if variant_sort_dir not in {"asc", "desc"}:
        variant_sort_dir = "asc"
    if comparison_sort_by not in DOCUMENT_COMPARISON_SORT_FIELDS:
        comparison_sort_by = "id"
    if comparison_sort_dir not in {"asc", "desc"}:
        comparison_sort_dir = "asc"

    comparisons_to_update = document.comparisons.filter(
        db.or_(TranslationComparison.bleu.is_(None), TranslationComparison.chrf.is_(None))
    ).all()
    if comparisons_to_update:
        for comparison in comparisons_to_update:
            if comparison.bleu is None:
                comparison.bleu = compute_bleu(
                    comparison.reference_variant.content,
                    comparison.candidate_variant.content,
                )
            if comparison.chrf is None:
                comparison.chrf = compute_chrf(
                    comparison.reference_variant.content,
                    comparison.candidate_variant.content,
                )
        db.session.commit()

    links = document.scan_links.order_by(DocumentScanLink.ordering.asc()).all()
    variants = document.translation_variants.order_by(*DOCUMENT_VARIANT_SORT_FIELDS[variant_sort_by](variant_sort_dir)).all()
    comparisons = document.comparisons.order_by(
        *DOCUMENT_COMPARISON_SORT_FIELDS[comparison_sort_by](comparison_sort_dir)
    ).all()
    previous_document, next_document = _document_neighbors(document.id, q, sort_by, sort_dir)
    return render_template(
        "documents/detail.html",
        document=document,
        links=links,
        variants=variants,
        comparisons=comparisons,
        q=q,
        sort_by=sort_by,
        sort_dir=sort_dir,
        previous_document=previous_document,
        next_document=next_document,
        variant_sort_by=variant_sort_by,
        variant_sort_dir=variant_sort_dir,
        comparison_sort_by=comparison_sort_by,
        comparison_sort_dir=comparison_sort_dir,
    )


@documents_bp.route("/<int:document_id>/edit", methods=["GET", "POST"])
def edit_document(document_id: int):
    document = Document.query.get_or_404(document_id)
    form = DocumentForm(obj=document)
    cancel_url = request.args.get("next") or url_for("documents.document_detail", document_id=document.id)
    if request.method == "GET":
        bind_version_token(form, document)
    if form.validate_on_submit():
        ensure_version_token_matches(form, document)
        form.populate_obj(document)
        if not document.document_code:
            document.document_code = None
        if not document.bibliographic_address:
            document.bibliographic_address = None
        db.session.commit()
        flash("Zapisano dokument.", "success")
        return redirect(url_for("documents.document_detail", document_id=document.id))
    return render_template("documents/form.html", form=form, title="Edycja dokumentu", cancel_url=cancel_url)


@documents_bp.route("/<int:document_id>/delete", methods=["POST"])
def delete_document(document_id: int):
    document = Document.query.get_or_404(document_id)
    db.session.delete(document)
    db.session.commit()
    flash("Usunięto dokument.", "success")
    return redirect(url_for("documents.list_documents"))


@documents_bp.route("/<int:document_id>/link-scans", methods=["GET", "POST"])
def link_scans(document_id: int):
    document = Document.query.get_or_404(document_id)
    linked_scan_ids = [link.scan_id for link in document.scan_links.all()]
    available_scans = Scan.query.filter(~Scan.id.in_(linked_scan_ids) if linked_scan_ids else True).order_by(Scan.id.asc()).all()
    cancel_url = url_for("documents.document_detail", document_id=document.id)

    form = LinkScanForm()
    form.scan_id.choices = [(scan.id, f"{scan.id} | {scan.title} | {scan.folio or '-'}") for scan in available_scans]

    if request.method == "POST" and not form.scan_id.choices:
        flash("Brak wolnych skanów do powiązania.", "warning")
        return redirect(url_for("documents.document_detail", document_id=document.id))

    if form.validate_on_submit():
        link = DocumentScanLink(
            document=document,
            scan_id=form.scan_id.data,
            ordering=form.ordering.data,
        )
        db.session.add(link)
        db.session.commit()
        flash("Powiązano skan z dokumentem.", "success")
        return redirect(url_for("documents.document_detail", document_id=document.id))

    return render_template(
        "documents/link_scans.html",
        document=document,
        form=form,
        cancel_url=cancel_url,
        title="Powiąż skan z dokumentem",
    )


@documents_bp.route("/links/<int:link_id>/edit", methods=["GET", "POST"])
def edit_link(link_id: int):
    link = DocumentScanLink.query.get_or_404(link_id)
    document = link.document
    cancel_url = url_for("documents.document_detail", document_id=document.id)

    linked_scan_ids = [item.scan_id for item in document.scan_links.filter(DocumentScanLink.id != link.id).all()]
    available_scans = Scan.query.filter(~Scan.id.in_(linked_scan_ids) if linked_scan_ids else True).order_by(Scan.id.asc()).all()

    form = LinkScanForm(obj=link)
    form.scan_id.choices = [(scan.id, f"{scan.id} | {scan.title} | {scan.folio or '-'}") for scan in available_scans]
    if request.method == "GET":
        bind_version_token(form, link)

    if form.validate_on_submit():
        ensure_version_token_matches(form, link)
        link.scan_id = form.scan_id.data
        link.ordering = form.ordering.data
        db.session.commit()
        flash("Zapisano powiązanie skanu z dokumentem.", "success")
        return redirect(url_for("documents.document_detail", document_id=document.id))

    return render_template(
        "documents/link_scans.html",
        document=document,
        form=form,
        cancel_url=cancel_url,
        title="Edycja powiązania skanu z dokumentem",
    )


@documents_bp.route("/links/<int:link_id>/delete", methods=["POST"])
def delete_link(link_id: int):
    link = DocumentScanLink.query.get_or_404(link_id)
    document_id = link.document_id
    db.session.delete(link)
    db.session.commit()
    flash("Usunięto powiązanie skanu z dokumentem.", "success")
    return redirect(url_for("documents.document_detail", document_id=document_id))


@documents_bp.route("/<int:document_id>/rebuild-original-text", methods=["POST"])
def rebuild_original_text(document_id: int):
    document = Document.query.get_or_404(document_id)
    submitted_token = (request.form.get("version_token") or "").strip()
    current_token = version_token_for(document)
    if submitted_token and submitted_token != current_token:
        raise ConcurrentUpdateError(
            "Ten dokument został zmieniony przez innego użytkownika. Odśwież widok i spróbuj ponownie."
        )

    links = document.scan_links.order_by(DocumentScanLink.ordering.asc()).all()
    if not links:
        flash("Nie można przebudować tekstu źródłowego, ponieważ dokument nie ma powiązanych skanów.", "warning")
        return redirect(url_for("documents.document_detail", document_id=document.id))

    texts: list[str] = []
    scans_without_primary_ground_truth: list[str] = []
    for link in links:
        chosen = _primary_ground_truth_for_scan(link.scan_id)
        if chosen is None or not (chosen.content or "").strip():
            scan_label = f"#{link.scan.id} — {link.scan.title}"
            scans_without_primary_ground_truth.append(scan_label)
            continue
        texts.append(chosen.content)

    if scans_without_primary_ground_truth:
        flash(
            "Nie można przebudować tekstu źródłowego. Następujące skany nie mają podstawowego wariantu ground truth: "
            + ", ".join(scans_without_primary_ground_truth),
            "warning",
        )
        return redirect(url_for("documents.document_detail", document_id=document.id))

    rebuilt_text = build_document_text_from_scan_texts(texts)
    if not rebuilt_text.strip():
        flash("Nie udało się zbudować tekstu źródłowego ze skanów, ponieważ podstawowe warianty ground truth są puste.", "warning")
        return redirect(url_for("documents.document_detail", document_id=document.id))

    current_original_text = (document.original_text or "").strip()
    confirm_overwrite = (request.form.get("confirm_overwrite") or "").strip() == "1"
    if current_original_text and not confirm_overwrite:
        flash("Tekst źródłowy dokumentu nie jest pusty. Potwierdź zastąpienie obecnej treści tekstem zbudowanym ze skanów.", "warning")
        return redirect(url_for("documents.document_detail", document_id=document.id))

    document.original_text = rebuilt_text
    db.session.commit()
    flash("Przebudowano tekst źródłowy dokumentu.", "success")
    return redirect(url_for("documents.document_detail", document_id=document.id))
