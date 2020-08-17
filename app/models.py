import requests
import random
import string
import sys
import json
import app
from datetime import datetime
from app import db
from flask_login import UserMixin
from app import login
from app import app

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), index=True, unique=True)
    access_key = db.Column(db.String(32))
    device_id = db.Column(db.String(24), unique=True)
    emby_id = db.Column(db.String(32), unique=True)
    sessions = db.relationship('Session', backref='owner', lazy='dynamic')

    def __repr__(self):
        return '<User {}>'.format(self.username)

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(32), index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String(32), db.ForeignKey('user.emby_id'))
    ticks = db.Column(db.BigInteger, default=0)
    room = db.Column(db.String(128))
    syncing = db.Column(db.Boolean, default=False)
    leader = db.Column(db.Boolean, default=False)
    item_id = db.Column(db.Integer)
    device_name = db.Column(db.String(128))
    client_name = db.Column(db.String(128))
    is_paused = db.Column(db.Boolean, default=False)
    playing = db.Column(db.Boolean, default=False)
    is_stale = db.Column(db.Boolean, default=False)
    is_dead = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return '<Session {}>'.format(self.session_id)

@login.user_loader
def load_user(id):
    return User.query.get(int(id))
