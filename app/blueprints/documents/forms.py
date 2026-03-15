from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional


class DocumentForm(FlaskForm):
    title = StringField("Tytuł", validators=[DataRequired()])
    document_code = StringField("Sygnatura źródła", validators=[Optional()])
    notes = TextAreaField("Uwagi", validators=[Optional()])
    is_done = BooleanField("Gotowe", default=False)
    original_text = TextAreaField("Tekst źródłowy", validators=[Optional()])
    submit = SubmitField("Zapisz")


class LinkScanForm(FlaskForm):
    scan_id = SelectField("Skan", coerce=int, validators=[DataRequired()])
    ordering = IntegerField("Kolejność", validators=[DataRequired()], default=1)
    submit = SubmitField("Zapisz")
