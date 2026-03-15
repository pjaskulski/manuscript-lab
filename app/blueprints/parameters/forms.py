from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField, SubmitField
from wtforms.validators import DataRequired


class ParameterModelForm(FlaskForm):
    version_token = HiddenField()
    name = StringField("Model", validators=[DataRequired()])
    submit = SubmitField("Zapisz")
