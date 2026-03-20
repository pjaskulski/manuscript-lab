from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired


class ParameterModelForm(FlaskForm):
    version_token = HiddenField()
    name = StringField("Model", validators=[DataRequired()])
    submit = SubmitField("Zapisz")


class ParameterPromptForm(FlaskForm):
    version_token = HiddenField()
    name = StringField("Nazwa promptu", validators=[DataRequired()])
    content = TextAreaField("Treść promptu", validators=[DataRequired()])
    submit = SubmitField("Zapisz")
