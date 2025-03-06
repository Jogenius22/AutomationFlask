from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, TimeField, BooleanField, FileField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError
import os
from flask import current_app

class AccountForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired()])
    capsolver_key = StringField('Capsolver API Key', validators=[Length(max=120)])
    active = BooleanField('Active', default=True)

class CityForm(FlaskForm):
    name = StringField('City Name', validators=[DataRequired(), Length(max=100)])
    radius = StringField('Radius (km)', validators=[DataRequired()])

class MessageForm(FlaskForm):
    content = TextAreaField('Message Content', validators=[DataRequired()])
    image = FileField('Attach Image')
    
    def validate_image(self, field):
        if field.data:
            filename = field.data.filename
            if filename != '':
                ext = filename.rsplit('.', 1)[1].lower()
                if ext not in current_app.config['ALLOWED_EXTENSIONS']:
                    raise ValidationError('File must be an image (png, jpg, jpeg, gif)')

class ScheduleForm(FlaskForm):
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    active = BooleanField('Active', default=True)

class SettingsForm(FlaskForm):
    run_interval = IntegerField('Run Interval (minutes)', 
                               validators=[DataRequired(),
                                           NumberRange(min=5, max=1440)])
    max_posts_per_day = IntegerField('Maximum Posts Per Day',
                                    validators=[DataRequired(),
                                                NumberRange(min=1, max=100)])
    timeout_between_actions = IntegerField('Timeout Between Actions (seconds)',
                                          validators=[DataRequired(),
                                                      NumberRange(min=1, max=60)])
    enable_random_delays = BooleanField('Enable Random Delays') 