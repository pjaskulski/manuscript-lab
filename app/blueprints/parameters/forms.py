from flask_wtf import FlaskForm
from wtforms import HiddenField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional


TRANSLATION_API_CHOICES = [
    ("", "- brak / ręczne -"),
    ("deepl-api", "DeepL API"),
    ("google-translate", "Google Translate"),
    ("gemini-api", "Gemini API"),
    ("openai-api", "OpenAI API"),
]


class ParameterModelForm(FlaskForm):
    version_token = HiddenField()
    name = StringField("Model", validators=[DataRequired()])
    api_definition = SelectField("Definicja API", choices=TRANSLATION_API_CHOICES, validators=[Optional()])
    model_code = StringField("Kod modelu", validators=[Optional()])
    submit = SubmitField("Zapisz")


class ParameterPromptForm(FlaskForm):
    version_token = HiddenField()
    name = StringField("Nazwa promptu", validators=[DataRequired()])
    content = TextAreaField("Treść promptu", validators=[DataRequired()])
    submit = SubmitField("Zapisz")
