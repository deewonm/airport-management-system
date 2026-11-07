from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, PasswordField, SubmitField, SelectField, SelectMultipleField, widgets
from wtforms.validators import InputRequired, DataRequired, EqualTo, NumberRange, Length

SKILLS = ["Tug", "Belt loader", "Baggage", "Steps"]

def clean(value):
    return value.strip() if isinstance(value, str) else value

def clean_code(value):
    value = clean(value)
    return value.upper() if value else value

# A list of checkboxes (used to pick skills)
class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

# LoginForm used to log into an existing account on the database.
class LoginForm(FlaskForm):
    airport_code = StringField("Airport Code:", filters=[clean_code], validators=[InputRequired(), Length(min=3, max=4)])
    employee_id = IntegerField("Employee ID:", validators=[InputRequired(), NumberRange(min=100000000, max=999999999)])
    password = PasswordField("Password:", validators=[InputRequired()])
    submit = SubmitField("Log in")

# RegistrationForm is used to create an account and to register it into the database.
# It reuses the login fields and adds the extra details needed for a new account.
class RegistrationForm(LoginForm):
    f_name = StringField("First Name:", filters=[clean], validators=[DataRequired()])
    s_name = StringField("Last Name:", filters=[clean], validators=[DataRequired()])
    role = SelectField("Role:", choices=[("ramp_agent", "Ramp Agent"), ("team_leader", "Team Leader")])
    skills = MultiCheckboxField("Skills:", choices=[(skill, skill) for skill in SKILLS])
    confirm_password = PasswordField("Confirm Password:", validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField("Register")
