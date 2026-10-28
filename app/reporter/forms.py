from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import HiddenField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models import CATEGORIES, PRIORITIES


class ComplaintForm(FlaskForm):
    title = StringField(
        "Specific problem title",
        validators=[DataRequired(), Length(max=160)],
        render_kw={"placeholder": "Example: Water leaking from ceiling in Block A Room 204"},
    )
    description = TextAreaField("Detailed description", validators=[DataRequired()])
    category = SelectField("Category", choices=[("", "Choose category")] + [(c, c) for c in CATEGORIES], validators=[DataRequired()])
    building = StringField("Building or block", validators=[DataRequired(), Length(max=120)])
    room_location = StringField("Room number or exact location", validators=[DataRequired(), Length(max=120)])
    priority = SelectField("Priority", choices=[("", "Choose priority")] + [(p, p) for p in PRIORITIES], validators=[DataRequired()])
    image = FileField("Optional photograph", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg"], "Images only.")])
    confirm_duplicate = StringField("Confirm duplicate", validators=[Optional()])
    predicted_category = HiddenField(validators=[Optional()])
    predicted_priority = HiddenField(validators=[Optional()])
    category_confidence = HiddenField(validators=[Optional()])
    priority_confidence = HiddenField(validators=[Optional()])
    submit = SubmitField("Submit complaint")


class FeedbackForm(FlaskForm):
    rating = IntegerField("Rating", validators=[DataRequired(), NumberRange(min=1, max=5)])
    comment = TextAreaField("Comment", validators=[Optional()])
    submit = SubmitField("Submit feedback")
