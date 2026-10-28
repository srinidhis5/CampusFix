from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.models import PRIORITIES


class AssignForm(FlaskForm):
    assignee_id = SelectField("Maintenance staff", coerce=int, validators=[DataRequired()])
    note = TextAreaField("Administrator note", validators=[Optional()])
    submit = SubmitField("Assign")


class PriorityForm(FlaskForm):
    priority = SelectField("Priority", choices=[(p, p) for p in PRIORITIES], validators=[DataRequired()])
    note = TextAreaField("Note", validators=[Optional()])
    submit = SubmitField("Change priority")


class StaffForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = EmailField("Email", validators=[DataRequired(), Length(max=180)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    department = StringField("Department", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    submit = SubmitField("Create account")
