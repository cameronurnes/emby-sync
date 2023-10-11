import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY')
    EMBY_SERVER = os.environ.get('EMBY_SERVER')
    DEFAULT_ROOM = os.environ.get('DEFAULT_ROOM') or 'Bacon Bar'
    INTERVAL = os.getenv("INTERVAL", "3.0")
    BUFFER = os.getenv("BUFFER", 0)
    SYNC_LIMIT = os.getenv("SYNC_LIMIT", "8")
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
