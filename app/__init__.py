from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from datetime import timedelta
from app.models import db 



#  Initialize Flask extensions
mail = Mail()
migrate = Migrate()

#  IST conversion for templates
def utc_to_ist(value):
    if value:
        return (value + timedelta(hours=5, minutes=30)).strftime('%d-%m-%Y %I:%M %p')
    return ""

def create_app():
    app = Flask(__name__)
    app.secret_key = ''  #  

    #  App configurations
    app.config.update({
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///bank.db',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,

        #  Gmail SMTP for OTP
        'MAIL_SERVER': 'smtp.gmail.com',
        'MAIL_PORT': 587,
        'MAIL_USE_TLS': True,
        'MAIL_USERNAME': '',  
        'MAIL_PASSWORD': ''  
    })

    #  Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    #  Register blueprints
    from app.routes import main
    app.register_blueprint(main)

    #  Jinja custom filter for IST
    app.jinja_env.filters['ist'] = utc_to_ist

    # Create tables (first-time only)
    with app.app_context():
        db.create_all()

    return app
