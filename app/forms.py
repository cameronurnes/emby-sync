from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('sign in')

class SessionList(FlaskForm):
    room_selection = SelectField('Existing Rooms')
    room_custom = StringField('New room name')
    session_id = SelectMultipleField('To select more than one, hold ⌘ on Mac or Ctrl on Windows')
    submit_room = SubmitField('Join room')
    submit_clear = SubmitField('Leave room')
    submit_clear_all = SubmitField('Unsync All')
    submit_leader = SubmitField('Select leader')
