from ..extensions import db
from .common import TimestampMixin


class ParameterModel(TimestampMixin, db.Model):
    __tablename__ = "parameter_models"
    __table_args__ = (
        db.UniqueConstraint("scope", "name", name="uq_parameter_models_scope_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return f"<ParameterModel {self.scope!r} {self.name!r}>"
