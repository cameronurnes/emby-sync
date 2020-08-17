import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY')
    EMBY_SERVER = os.environ.get('EMBY_SERVER') or 'http://127.0.0.1:8096'
    DEFAULT_ROOM = os.environ.get('DEFAULT_ROOM') or 'Bacon Bar'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
