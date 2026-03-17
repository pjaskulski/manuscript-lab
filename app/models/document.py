from ..extensions import db
from .common import TimestampMixin


class Document(TimestampMixin, db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    document_code = db.Column(db.String(128), nullable=True, unique=True)
    bibliographic_address = db.Column(db.String(512), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_done = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    original_text = db.Column(db.Text, nullable=True, default="")
    scan_links = db.relationship(
        "DocumentScanLink",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentScanLink.ordering",
        lazy="dynamic",
    )
    translation_variants = db.relationship(
        "TranslationVariant",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    comparisons = db.relationship(
        "TranslationComparison",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Document {self.id} {self.title!r}>"


class DocumentScanLink(TimestampMixin, db.Model):
    __tablename__ = "document_scan_links"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    scan_id = db.Column(db.Integer, db.ForeignKey("scans.id"), nullable=False)
    ordering = db.Column(db.Integer, nullable=False, default=1)
    role = db.Column(db.String(50), nullable=True)

    document = db.relationship("Document", back_populates="scan_links")
    scan = db.relationship("Scan", back_populates="document_links")

    __table_args__ = (
        db.UniqueConstraint("document_id", "scan_id", name="uq_document_scan"),
    )

    def __repr__(self):
        return f"<DocumentScanLink doc={self.document_id} scan={self.scan_id}>"
