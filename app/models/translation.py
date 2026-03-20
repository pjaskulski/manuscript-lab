from ..extensions import db
from .common import TimestampMixin


class TranslationVariant(TimestampMixin, db.Model):
    __tablename__ = "translation_variants"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)

    variant_type = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False, default="")

    source_tool = db.Column(db.String(128), nullable=True)
    source_model = db.Column(db.String(128), nullable=True)
    source_prompt = db.Column(db.String(128), nullable=True)

    document = db.relationship("Document", back_populates="translation_variants")
    reference_comparisons = db.relationship(
        "TranslationComparison",
        foreign_keys="TranslationComparison.reference_variant_id",
        back_populates="reference_variant",
        lazy="dynamic",
    )
    candidate_comparisons = db.relationship(
        "TranslationComparison",
        foreign_keys="TranslationComparison.candidate_variant_id",
        back_populates="candidate_variant",
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
    def source_summary(self) -> str | None:
        source = self.source_display
        prompt = (self.source_prompt or "").strip()
        if source and prompt:
            return f"{source} / prompt: {prompt}"
        return source or (f"prompt: {prompt}" if prompt else None)

    def __repr__(self):
        return f"<TranslationVariant {self.id} {self.variant_type!r}>"


class TranslationComparison(TimestampMixin, db.Model):
    __tablename__ = "translation_comparisons"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    reference_variant_id = db.Column(
        db.Integer,
        db.ForeignKey("translation_variants.id"),
        nullable=False,
    )
    candidate_variant_id = db.Column(
        db.Integer,
        db.ForeignKey("translation_variants.id"),
        nullable=False,
    )

    bleu = db.Column(db.Float, nullable=True)
    chrf = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    document = db.relationship("Document", back_populates="comparisons")
    reference_variant = db.relationship(
        "TranslationVariant",
        foreign_keys=[reference_variant_id],
        back_populates="reference_comparisons",
    )
    candidate_variant = db.relationship(
        "TranslationVariant",
        foreign_keys=[candidate_variant_id],
        back_populates="candidate_comparisons",
    )

    def __repr__(self):
        return f"<TranslationComparison {self.id}>"
