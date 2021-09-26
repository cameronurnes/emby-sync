from typing import Tuple, Union
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

def check_password(username, password) -> Tuple[bool, Union[User, None]]:
    """
    Returns:
        authentication status: True or False
        user or None
    """
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
        new, user = update_or_create_account(response_json)
        return True, user
    else:
        print(response.text, flush=True)
        return False, None

def update_or_create_account(response)-> Tuple[bool, User]:
    """
    Returns:
        newuser: True, False
        user: the user object
    """
    user = db.session.query(User).filter_by(username=response['User']['Name'].lower()).first()
    if user:
        user.device_id = response['SessionInfo']['DeviceId']
        user.access_key = response['AccessToken']
        db.session.commit()
        update_or_create_sessions()
        return True, user
    else:
        newuser = User(emby_id=response['User']['Id'], username=response['User']['Name'].lower(), access_key=response['AccessToken'], device_id=response['SessionInfo']['DeviceId'])
        db.session.add(newuser)
        db.session.commit()
        return True, newuser

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


def comparetoleader(leader_session : Session, follower_session : Session, follower: User):
    """
    Compares the follower state to the leader
    Makes the follower pause, unpause
    Sync or play the same item as the leader
    """
    if (leader_session.playing == False) and (follower_session.playing == True):
        # If the leader isn't playing and the follower is playing
        # stop their player
        app.apscheduler.add_job(func=send_command, trigger='date',\
                args=[follower_session.session_id, "Stop"],\
                id="Stop "+follower_session.session_id+" "+leader_session.session_id)
        follower_session.syncing = False
        db.session.commit()
    if  (leader_session.playing == True) and (follower_session.playing == True)\
            and (leader_session.item_id != follower_session.item_id):
        # If the leader isn't playing the same item as the leader,
        # force it to play the same item
        app.apscheduler.add_job(func=startplay_w_pause, trigger='date',\
                args=[follower_session.session_id, leader_session.ticks, leader_session.item_id, leader_session.is_paused, 10000],\
                id="PlaywPause "+follower_session.session_id+" "+leader_session.session_id)

    elif (leader_session.playing == True) and (follower_session.playing == True)\
            and (leader_session.item_id == follower_session.item_id)\
            and (leader_session.is_paused == True and leader_session.is_paused == False):
        # Leader is playing but paused. Follower is playing
        # and not yet paused
        # Pause the follower and seek it to the leader
        # Pause and seek session to leader
        app.apscheduler.add_job(func=pause_and_sync, trigger='date',\
                args=[follower_session.session_id, leader_session.ticks],\
                id="PauseNSync "+follower_session.session_id+" "+leader_session.session_id)
        follower_session.syncing = False
        db.session.commit()
    elif (leader_session.playing == True) and (follower_session.playing == False) and (leader_session.ticks != 0):
        # Leader is playing, this session is not yet playing
        # Start playing at the same point as the leader
        app.apscheduler.add_job(func=ensure_play, trigger='date',\
            args=[follower_session.session_id, leader_session.ticks, leader_session.item_id],\
            id="Startplay "+follower_session.session_id+" "+leader_session.session_id)

        follower_session.syncing = True
        db.session.commit()
    elif (leader_session.playing == True) and (follower_session.playing == True)\
        and (leader_session.is_paused == False and follower_session.is_paused == True):
        # Leader is not paused, session is paused.
        # Resume the session
        app.apscheduler.add_job(func=send_command, trigger='date',\
                args=[follower_session.session_id, "Unpause"],\
                id="Pause "+follower_session.session_id+" "+leader_session.session_id)

    elif (leader_session.playing == True) and (follower_session.playing == True) and (leader_session.ticks != 0):
        sync_drift = check_sync(follower_session.ticks, leader_session.ticks)
        if sync_drift >= 8:
            print(follower.username+" "+follower_session.device_name+" sync difference too much ({}), syncing ".format(sync_drift))
            app.apscheduler.add_job(func=set_playtime, trigger='date',\
                args=[follower_session.session_id, leader_session.ticks],\
                id="Sync "+follower_session.session_id+" "+leader_session.session_id)
            follower_session.syncing = True
            db.session.commit()
    else:
        print("Unknown situation")


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
                    comparetoleader(leader_session, z, session_user)

def check_sync(follower_ticks: int, leader_ticks: int):
    drift = abs((follower_ticks/10000000) - (leader_ticks/10000000))
    return drift


def pause_and_sync(follower_id, time:int):
    send_command(follower_id, "Pause")
    # Now sync
    set_playtime(follower_id, time=time)


def startplay_w_pause(session: int, time: int, item_id: int, pause: bool, buffer=0):
    """
    Tell the session to play the item at the given time
    If buffer is given, add that amount of time to give the follower time to buffer
    Roughly 10000 ticks is 1 second
    """
    target = time + buffer
    start_play(
        session,
        time=target,
        item_id=item_id
    )
    # If the leader is paused, also tell the follower to pause
    if (pause == True):
        send_command(session.session_id, "Pause")


def ensure_play(session: int, time: int, item_id: int, maxretries=8):
    """
    Retry start_play until succesful or the maxretries is hit
    """
    success = False
    retries = 0
    while (success and retries < maxretries):
        success = start_play(session, time, item_id)
        retries += 1


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
