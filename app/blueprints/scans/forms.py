from flask_wtf import FlaskForm
from pathlib import Path

from flask_wtf.file import FileAllowed, FileField, MultipleFileField
from wtforms import BooleanField, HiddenField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional, ValidationError

ALLOWED_SCAN_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "tif", "tiff"]
MAX_BULK_IMPORT_FILES = 10


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
        validators=[FileAllowed(ALLOWED_SCAN_EXTENSIONS, "Niedozwolony format.")],
    )
    submit = SubmitField("Zapisz")


class BulkScanImportForm(FlaskForm):
    shelfmark = StringField("Sygnatura domyślna", validators=[Optional()])
    hand = StringField("Ręka domyślna", validators=[Optional()])
    notes = TextAreaField("Wspólne uwagi", validators=[Optional()])
    is_training_sample = BooleanField("Do próbki uczącej")
    image_files = MultipleFileField(
        "Pliki skanów",
        validators=[FileAllowed(ALLOWED_SCAN_EXTENSIONS, "Niedozwolony format.")],
    )
    submit = SubmitField("Importuj skany")

    def validate_image_files(self, field):
        files = [file for file in field.data if file and file.filename]
        if not files:
            raise ValidationError("Wybierz przynajmniej jeden plik.")
        if len(files) > MAX_BULK_IMPORT_FILES:
            raise ValidationError(f"Możesz zaimportować maksymalnie {MAX_BULK_IMPORT_FILES} plików naraz.")
        invalid = []
        for file in files:
            suffix = Path(file.filename).suffix.lower().lstrip(".")
            if suffix not in ALLOWED_SCAN_EXTENSIONS:
                invalid.append(file.filename)
        if invalid:
            raise ValidationError(f"Niedozwolony format pliku: {', '.join(invalid)}.")


class ScanTrainingExportForm(FlaskForm):
    include_images = BooleanField("Dołącz pliki skanów")
    submit = SubmitField("Przygotuj paczkę ZIP")
