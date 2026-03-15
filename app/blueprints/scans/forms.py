from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, HiddenField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional


class ScanForm(FlaskForm):
    version_token = HiddenField()
    title = StringField("Tytuł", validators=[DataRequired()])
    shelfmark = StringField("Sygnatura", validators=[Optional()])
    folio = StringField("Folio", validators=[Optional()])
    sequence_no = IntegerField("Kolejność", validators=[Optional()])
    hand = StringField("Ręka", validators=[Optional()])
    notes = TextAreaField("Uwagi", validators=[Optional()])
    is_training_sample = BooleanField("Do próbki uczącej")
    is_done = BooleanField("Gotowe")
    image_file = FileField(
        "Obraz skanu",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp", "tif", "tiff"], "Niedozwolony format.")],
    )
    submit = SubmitField("Zapisz")


class ScanTrainingExportForm(FlaskForm):
    include_images = BooleanField("Dołącz pliki skanów")
    submit = SubmitField("Przygotuj paczkę ZIP")
