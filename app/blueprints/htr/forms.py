from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional


TEXT_TYPES = [
    ("ground_truth", "Ground truth"),
    ("ground_truth_diplomatic", "Ground truth, zapis dyplomatyczny"),
    ("ground_truth_expanded", "Ground truth, zapis rozwinięty"),
    ("htr_model_output", "Wynik modelu HTR"),
]

NORMALIZATION_PROFILES = [
    ("raw", "raw"),
    ("lowercase", "lowercase"),
    ("lowercase_no_punct", "lowercase_no_punct"),
]

GROUND_TRUTH_TEXT_TYPES = {
    "ground_truth",
    "ground_truth_diplomatic",
    "ground_truth_expanded",
}


class ScanTextForm(FlaskForm):
    text_type = SelectField("Typ tekstu", validators=[DataRequired()], choices=TEXT_TYPES)
    label = StringField("Uwagi", validators=[Optional()])
    source_model = SelectField("Model", validators=[DataRequired()], choices=[])
    main_ground_truth = BooleanField("Podstawowa wersja ground truth", default=False)
    is_line_based = BooleanField("Tekst poliniowany", default=True)
    content = TextAreaField("Treść", validators=[DataRequired()])
    submit = SubmitField("Zapisz")


class ScanTextWorkspaceForm(FlaskForm):
    content = TextAreaField("Treść", validators=[DataRequired()])
    submit = SubmitField("Zapisz")


class HTRCompareForm(FlaskForm):
    reference_text_id = SelectField("Tekst wzorcowy", coerce=int, validators=[DataRequired()])
    candidate_text_id = SelectField("Tekst porównywany", coerce=int, validators=[DataRequired()])
    normalization_profile = SelectField(
        "Profil normalizacji",
        validators=[DataRequired()],
        choices=NORMALIZATION_PROFILES,
        default="lowercase",
    )
    submit = SubmitField("Porównaj")
