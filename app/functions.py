import app
import datetime
import random
import platform
import requests
import json
import string
import threading
import time
from app import app
from app import db
from app import functions
from app.models import User, Session
from flask_login import current_user

def check_password(username, password):
    url = '{0}/Users/Authenticatebyname'.format(app.config['EMBY_SERVER'])
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': ''.join(random.choices(string.ascii_uppercase + string.digits, k = 24)),
        'X-Emby-Device-Name': 'Emby Sync'
    }
    data = { 'Username': username, 'Pw': password }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        response_json = response.json()
        update_or_create_account(response_json)
        return True
    else:
        print(response.text, flush=True)
        return False

def update_or_create_account(response):
    user = db.session.query(User).filter_by(username=response['User']['ConnectUserName'].lower()).first()
    if user:
        user.device_id = response['SessionInfo']['DeviceId']
        user.access_key = response['AccessToken']
        db.session.commit()
        update_or_create_sessions()
        return True
    else:
        newuser = User(emby_id=response['User']['Id'], username=response['User']['ConnectUserName'].lower(), access_key=response['AccessToken'], device_id=response['SessionInfo']['DeviceId'])
        db.session.add(newuser)
        db.session.commit()
        return True

def end_session():
    for z in current_user.sessions:
            set_dead(z.session_id)
            db.session.commit()
            session_cleanup()

    url = '{0}/Sessions/Logout'.format(app.config['EMBY_SERVER'])
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': current_user.device_id,
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Token': current_user.access_key
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        return True
    else:
        print(response.text, flush=True)
        return False

def update_or_create_sessions():
    emby_session = db.session.query(Session).filter_by(device_id='session-sync').all()
    for z in emby_session:
        try:
            set_room(app.config['DEFAULT_ROOM'], z.session_id)
        except KeyError:
            continue
    url = '{0}/Sessions'.format(app.config['EMBY_SERVER'])
    headers = {
        'accept': 'applicaton/json',
        'X-Emby-Token': app.config['SECRET_KEY'],
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Client': platform.system()
    }
    response = requests.get(url, headers=headers)
    response_json = response.json()
    for z in response_json:
        try:
            emby_session = db.session.query(Session).filter_by(session_id=z['Id']).first()
            date_time_obj = datetime.datetime.fromisoformat(z['LastActivityDate'][:-2])
            if stale_calc(date_time_obj, 300):
                continue
            if emby_session:
                emby_session.timestamp = date_time_obj
                db.session.commit()
                if 'NowPlayingItem' in z:
                    emby_session.playing = True
                    emby_session.item_id = z['NowPlayingItem']['Id']
                    emby_session.ticks = z['PlayState']['PositionTicks']
                    emby_session.is_paused = z['PlayState']['IsPaused']
                    db.session.commit()
                else:
                    emby_session.playing = False
                    emby_session.item_id = None
                    emby_session.ticks = None
                    emby_session.is_paused = z['PlayState']['IsPaused']
                    db.session.commit()
            else:
                if z['DeviceId'] != 'session-sync':
                    newsession = Session(user_id=z['UserId'], session_id=z['Id'], device_name=z['DeviceName'], timestamp=date_time_obj, client_name=z['Client'], device_id=z['DeviceId'])
                    db.session.add(newsession)
                    db.session.commit()
                else:
                    newsession = Session(session_id=z['Id'], device_name=z['DeviceName'], timestamp=date_time_obj, client_name=z['Client'], device_id=z['DeviceId'])
                    db.session.add(newsession)
                    db.session.commit()

        except KeyError:
            continue

def set_leader(room_name, emby_session_id):
    emby_session = db.session.query(Session).filter_by(room=room_name, leader=True).first()
    if emby_session:
        emby_session.leader = False
        db.session.commit()
        emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
        emby_session.room = room_name
        emby_session.leader = True
        db.session.commit()
    return True

def set_room(room_name, emby_session_id):
    emby_session = db.session.query(Session).filter_by(room=room_name, leader=True).first()
    if emby_session:
        emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
        emby_session.room = room_name
        emby_session.leader = False
        db.session.commit()
    else:
        emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
        emby_session.room = room_name
        if (emby_session.device_name != 'Emby Sync'):
            emby_session.leader = True
        db.session.commit()
    return True

def stale_check(in_sesh):
    if (in_sesh.is_stale == False) and (stale_calc(in_sesh.timestamp, 300)):
        in_sesh.is_stale = True
        db.session.commit()
    if (in_sesh.is_stale == True) and not (stale_calc(in_sesh.timestamp, 120)):
        in_sesh.is_stale = False
        db.session.commit()
    if (in_sesh.is_stale == True) and (stale_calc(in_sesh.timestamp, 600)):
        set_dead(in_sesh.session_id)
        session_cleanup()
    return True

def stale_calc(time, limit):
    staleTime = datetime.datetime.utcnow() - time
    staleTime = abs(staleTime.total_seconds())
    if staleTime > limit:
        return True
    else:
        return False

def set_dead(emby_session_id):
    emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
    emby_session.is_dead = True
    db.session.commit()
    return True

def session_cleanup():
    Session.query.filter(Session.is_dead==True).delete()
    db.session.commit()

def sync_cycle():
    update_or_create_sessions()
    session_list = Session.query.all()
    for z in session_list:
        stale_check(z)
        if (z.leader == True) or (z.device_id == 'session-sync'):
            continue
        else:
            if (z.room != None) and (z.is_stale == False):
                leader_session = db.session.query(Session).filter_by(room=z.room, leader=True).first()
                session_user = db.session.query(User).filter_by(emby_id=z.user_id).first()
                if leader_session:
                    if (leader_session.playing == False) and (z.playing == True):
                        send_command(z.session_id, "Stop")
                        z.syncing = False
                        db.session.commit()
                    if (leader_session.playing == True) and (z.playing == True) and (leader_session.is_paused == True):
                        # Leader is playing, but paused, session is currently playing
                        # Pause and seek session to leader
                        #TODO: this should ensure the follower is playing the same item as the leader
                        send_command(z.session_id, "Pause")
                        # Now sync
                        set_playtime(z.session_id, time=leader_session.ticks)
                        z.syncing = False
                        db.session.commit()
                    if (leader_session.playing == True) and (z.playing == False) and (leader_session.ticks != 0):
                        # Leader is playing, this session is not yet playing
                        # Sync session to leader
                        app.apscheduler.add_job(func=sync, trigger='date', args=[z, z.session_id, leader_session.ticks, leader_session.item_id], id="Sync "+z.session_id+" "+leader_session.session_id)
                        z.syncing = True
                        db.session.commit()
                    if (leader_session.playing == True) and (z.playing == True) and (leader_session.ticks != 0):
                        #TODO: if ensured the follower is playing the same item as the leader, seek would be more efficient
                        # than sync
                        sync_drift = check_sync(z.ticks, leader_session.ticks)
                        print(session_user.username+" "+z.device_name+" sync: "+str(sync_drift))
                        if sync_drift >= 8:
                            app.apscheduler.add_job(func=sync, trigger='date', args=[z, z.session_id, leader_session.ticks, leader_session.item_id], id="Sync "+z.session_id+" "+leader_session.session_id)
                            z.syncing = True
                            db.session.commit()

def check_sync(follow_session, leader_session):
    drift = abs((follow_session/10000000) - (leader_session/10000000))
    return drift

def sync(follow_session, follow_id, leader_ticks, leader_item):
    """
    Forces the following session to start playing the leaders item
    at the leaders tick.
    Does a few pauses and unpauses
    """
    target = leader_ticks + (10*10000000)
    set_playtime(follow_id, target, leader_item)
    for i in range(8):
        send_command(follow_id, "Pause")
        time.sleep(1)
    follow_session.syncing = False
    db.session.commit()
    for i in range(2):
        send_command(follow_id, "Unpause")
        time.sleep(1)

def start_play(session: int, time: int, item_id: int) -> bool:
    """
    Tell the session client to play the given item id at the given time
    """
    url = '{0}/Sessions/{1}/Playing'.format(app.config['EMBY_SERVER'], session)
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Token': app.config['SECRET_KEY']
    }
    params = {
        'ItemIds': item_id,
        'StartPositionTicks': time
    }
    response = requests.post(url, headers=headers, params=params)
    if response.status_code == 204:
        return True
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)
        return False


def set_playtime(session: int, time: int) -> bool:
    """
    Tell the session to jump (seek) to the already playing item
    Args:
        session: session id
        time: time in ticks to seek
    Returns:
        result: True if successful, False if not
    """
    url = '{0}/Sessions/{1}/Playing/Seek'.format(app.config['EMBY_SERVER'], session)
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Token': app.config['SECRET_KEY']
    }
    params = {
        'SeekPositionTicks': time
    }
    response = requests.post(url, headers=headers, params=params)
    if response.status_code == 204:
        return True
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)
        return False

def send_command(session, command):
    url = '{0}/Sessions/{1}/Playing/{2}'.format(app.config['EMBY_SERVER'], session, command)
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Token': app.config['SECRET_KEY']
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 204:
        return True
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)
        return False


def get_room_leader(room):
    leader_session = db.session.query(Session).filter_by(room=room, leader=True).first()
    if leader_session and leader_session.device_name != 'Emby Connect':
        leader_user = db.session.query(User).filter_by(emby_id=leader_session.user_id).first()
        return "  --  Current leader is {0}".format(leader_user.username)
    else:
        return ""

def get_room_name(session):
    if session.room and session.leader != True:
        return " -- Synced to {0}".format(session.room)
    if session.room and session.leader == True:
        return " -- Leading {0}".format(session.room)
    else:
        return " -- Not Synced"
