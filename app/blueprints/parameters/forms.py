from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired


class ParameterModelForm(FlaskForm):
    name = StringField("Model", validators=[DataRequired()])
    submit = SubmitField("Zapisz")
