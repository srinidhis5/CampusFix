from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional


class ProgressForm(FlaskForm):
    note = TextAreaField("Progress note", validators=[DataRequired()])
    completion_image = FileField("Completion proof", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg"], "Images only.")])
    mark_resolved = BooleanField("Mark as resolved")
    submit = SubmitField("Save update")
