from flask import Blueprint, render_template

from ...models import Document, Scan

main_bp = Blueprint("main", __name__, template_folder="templates")

@main_bp.route("/")
def index():
    scans_count = Scan.query.count()
    documents_count = Document.query.count()
    return render_template(
        "main/index.html",
        scans_count=scans_count,
        documents_count=documents_count,
    )
