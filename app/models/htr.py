from ..extensions import db
from .common import TimestampMixin


class HTRComparison(TimestampMixin, db.Model):
    __tablename__ = "htr_comparisons"

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("scans.id"), nullable=False)
    reference_text_id = db.Column(db.Integer, db.ForeignKey("scan_texts.id"), nullable=False)
    candidate_text_id = db.Column(db.Integer, db.ForeignKey("scan_texts.id"), nullable=False)

    cer = db.Column(db.Float, nullable=True)
    wer = db.Column(db.Float, nullable=True)
    normalization_profile = db.Column(db.String(64), nullable=True)
    diff_html = db.Column(db.Text, nullable=True)

    scan = db.relationship("Scan", back_populates="comparisons")
    reference_text = db.relationship(
        "ScanText",
        foreign_keys=[reference_text_id],
        back_populates="reference_comparisons",
    )
    candidate_text = db.relationship(
        "ScanText",
        foreign_keys=[candidate_text_id],
        back_populates="candidate_comparisons",
    )

    def __repr__(self):
        return f"<HTRComparison {self.id}>"
