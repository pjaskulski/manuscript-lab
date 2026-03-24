from flask_wtf import FlaskForm
from wtforms import HiddenField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional


VARIANT_TYPES = [
    ("reference", "Referencyjne"),
    ("model_output", "Wynik modelu"),
]


class TranslationVariantForm(FlaskForm):
    version_token = HiddenField()
    auto_source_tool = HiddenField()
    variant_type = SelectField("Typ wariantu", choices=VARIANT_TYPES, validators=[DataRequired()])
    source_model = SelectField("Model", choices=[], validators=[Optional()])
    source_prompt = SelectField("Prompt", choices=[], validators=[Optional()])
    label = StringField("Uwagi", validators=[Optional()])
    content = TextAreaField("Treść", validators=[DataRequired()])
    translate_submit = SubmitField("Przetłumacz automatycznie")
    submit = SubmitField("Zapisz")


class TranslationCompareForm(FlaskForm):
    reference_variant_id = SelectField("Wariant referencyjny", coerce=int, validators=[DataRequired()])
    candidate_variant_id = SelectField("Wariant porównywany", coerce=int, validators=[DataRequired()])
    notes = TextAreaField("Uwagi", validators=[Optional()])
    submit = SubmitField("Porównaj")
