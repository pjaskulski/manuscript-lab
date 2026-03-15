from ..extensions import db
from .common import TimestampMixin


class Scan(TimestampMixin, db.Model):
    __tablename__ = "scans"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    shelfmark = db.Column(db.String(255), nullable=True)
    folio = db.Column(db.String(64), nullable=True)
    sequence_no = db.Column(db.Integer, nullable=True)
    hand = db.Column(db.String(128), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_training_sample = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    is_done = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    image_path = db.Column(db.String(512), nullable=True)
    image_width = db.Column(db.Integer, nullable=True)
    image_height = db.Column(db.Integer, nullable=True)

    texts = db.relationship(
        "ScanText",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    document_links = db.relationship(
        "DocumentScanLink",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    comparisons = db.relationship(
        "HTRComparison",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Scan {self.id} {self.title!r}>"


class ScanText(TimestampMixin, db.Model):
    __tablename__ = "scan_texts"

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("scans.id"), nullable=False)

    text_type = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False, default="")
    is_line_based = db.Column(db.Boolean, default=True, nullable=False)
    main_ground_truth = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())

    source_tool = db.Column(db.String(128), nullable=True)
    source_model = db.Column(db.String(128), nullable=True)

    scan = db.relationship("Scan", back_populates="texts")
    reference_comparisons = db.relationship(
        "HTRComparison",
        foreign_keys="HTRComparison.reference_text_id",
        back_populates="reference_text",
        lazy="dynamic",
    )
    candidate_comparisons = db.relationship(
        "HTRComparison",
        foreign_keys="HTRComparison.candidate_text_id",
        back_populates="candidate_text",
        lazy="dynamic",
    )

    @property
    def source_display(self) -> str | None:
        model = (self.source_model or "").strip()
        tool = (self.source_tool or "").strip()
        if model and tool and tool.lower() not in model.lower():
            return f"{tool} / {model}"
        return model or tool or None

    @property
    def comparison_display(self) -> str:
        model = self.source_display
        label = (self.label or "").strip()
        if model and label:
            return f"{model} | {label}"
        if model:
            return model
        if label:
            return label
        return self.text_type

    def __repr__(self):
        return f"<ScanText {self.id} {self.text_type!r}>"
