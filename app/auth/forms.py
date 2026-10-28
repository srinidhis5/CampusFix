from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Length(max=180)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")


class RegisterForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = EmailField("Email", validators=[DataRequired(), Length(max=180)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])
    department = StringField("Department", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    submit = SubmitField("Register")
