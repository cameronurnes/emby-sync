from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from flask_bootstrap import Bootstrap
import signal
import sys
import logging

app = Flask(__name__)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
app.config.from_object(Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login'
bootstrap = Bootstrap(app)
INTERVAL = .05

from app.functions import * 
logging.getLogger().setLevel(logging.ERROR)
app.apscheduler.add_job(func=sync_cycle, trigger='interval', seconds=INTERVAL, id='sync_cycle')

## Needed to run application
from app import routes, models, functions