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
    user = db.session.query(User).filter_by(username=response['User']['Name'].lower()).first()
    if user:
        user.device_id = response['SessionInfo']['DeviceId']
        user.access_key = response['AccessToken']
        db.session.commit()
        update_or_create_sessions()
        return True
    else:
        newuser = User(emby_id=response['User']['Id'], username=response['User']['Name'].lower(), access_key=response['AccessToken'], device_id=response['SessionInfo']['DeviceId'])
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

def getUserJson():
    url = '{0}/Users'.format(app.config['EMBY_SERVER'])
    headers = {
        'accept': 'applicaton/json',
        'X-Emby-Token': app.config['SECRET_KEY'],
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Client': platform.system()
    }
    response = requests.get(url, headers=headers)
    response_json = response.json()

    return response_json

def getSessionJson():
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

    return response_json

def getSessionList():
    sessions = getSessionJson()
    embySessionList = []
    for session in sessions:
        try:
            emby_session = db.session.query(Session).filter_by(session_id=session['Id']).first()
            
            ## Checking if the emby_session isn't None
            if(emby_session):
                embySessionList.append(emby_session)

        except KeyError:
            pass
    
    return embySessionList

def printJsonResponce(responce):
    print(json.dumps(responce,indent=3))

def update_or_create_sessions():
    ## Just for the Emby Sync user aka the bot
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

    active_users = []
    for z in response_json:
        try:
            emby_session = db.session.query(Session).filter_by(session_id=z['Id']).first()
            date_time_obj = datetime.datetime.fromisoformat(z['LastActivityDate'][:-2])
            ip_obj = z['RemoteEndPoint']
            if stale_calc(date_time_obj, 300):
                continue
            if emby_session:
                emby_session.timestamp = date_time_obj
                emby_session.ip_address = ip_obj
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
                    newsession = Session(user_id=z['UserId'], session_id=z['Id'], device_name=z['DeviceName'], timestamp=date_time_obj, client_name=z['Client'], device_id=z['DeviceId'], ip_address=ip_obj)
                    db.session.add(newsession)
                    db.session.commit()

                else:
                    newsession = Session(session_id=z['Id'], device_name=z['DeviceName'], timestamp=date_time_obj, client_name=z['Client'], device_id=z['DeviceId'], ip_address=ip_obj)
                    db.session.add(newsession)
                    db.session.commit()

            active_users.append(z['Id'])

        except KeyError:
            continue
    
    return active_users

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

        ## For when a new person joins that isn't the leader
        if(emby_session.device_id != 'session-sync'):
            send_command(emby_session.session_id, "Message")

    ## No leader exists
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
    active_users = update_or_create_sessions()
    full_session_list = Session.query.all()

    ## This will only get the users that are actually connected to the Emby server
    current_session_list = [session for session in full_session_list if(session.session_id in active_users)]
    for z in current_session_list:
        # stale_check(z)
        # print(z.session_id)

        ## This is just for the leader/emby-sync, so nothing happens
        if (z.leader == True) or (z.device_id == 'session-sync'):
            continue
        ## This is just for the followers
        else:
            if (z.room != None) and (z.is_stale == False):
                leader_session = db.session.query(Session).filter_by(room=z.room, leader=True).first()
                session_user = db.session.query(User).filter_by(emby_id=z.user_id).first()
                if leader_session:

                    ## Leader are Follower are not currently in any video
                    if(leader_session.playing == False) and (z.playing == False):
                        pass
                    ## This is for when the follower tries to start playing when synced to a room. This forces the follower to follow the leader
                    if(leader_session.playing == False) and (z.playing == True):
                        print("STOP")
                        send_command(z.session_id, "Stop")
                        z.syncing = False
                        db.session.commit()
                    ## This is for when the leader pauses and forces the follower to pause
                    if(leader_session.playing == True) and (leader_session.is_paused == True) and (z.playing == True) and (z.is_paused == False):
                        print("PAUSE")
                        send_command(z.session_id, "Pause")
                        z.syncing = False
                        db.session.commit()
                    ## This if for when the leader resumes from a paused state
                    if(leader_session.playing == True) and (leader_session.is_paused == False) and (z.playing == True) and (z.is_paused == True) and (z.syncing == False):
                        print("RESUME")
                        send_command(z.session_id, "Unpause")
                        z.syncing = True
                        db.session.commit()
                    ## This if for when the leader starts playing and the follower is does not have any video loaded
                    if(leader_session.playing == True) and (leader_session.is_paused == False) and (z.playing == False) and (leader_session.ticks != 0):
                        print("FOLLOWER NEEDS TO START PLAYING")
                        send_command(leader_session.session_id,"Pause")
                        app.apscheduler.add_job(func=sync, trigger='date', args=[z, z.session_id, leader_session.session_id, leader_session.ticks, leader_session.item_id], id="Sync "+z.session_id+" "+leader_session.session_id)
                        z.syncing = True
                        db.session.commit()
                    if(leader_session.playing == True) and (z.playing == True) and (leader_session.ticks != 0):
                        sync_drift = check_sync(z.ticks, leader_session.ticks)
                        print(f"Follower: {session_user.username} {z.device_name} drift: {sync_drift}")
                        # if abs(sync_drift) >= 12:
                        #     app.apscheduler.add_job(func=sync, trigger='date', args=[z, z.session_id, leader_session.session_id, leader_session.ticks, leader_session.item_id], id="Sync "+z.session_id+" "+leader_session.session_id)
                        #     z.syncing = True
                        #     db.session.commit()

def check_sync(follow_session, leader_session):
    drift = (follow_session/10000000) - (leader_session/10000000)
    return drift

def sync(follow_session, follow_id, leader_session, leader_ticks, leader_item):
    target = leader_ticks + (3*10000000) # Load 10 seconds ahead to give user time to buffer
    set_playtime(follow_id, target, leader_item)

    print("PAUSING")
    end = time.time() + 3 ## Adding 10 seconds to the current time
    while((time.time() < end) or (follow_session.ticks == None)):
        send_command(follow_id, "Pause")
        time.sleep(0.5)
        send_command(follow_id, "Pause")
        time.sleep(0.5)

    # for i in range(8):
    #     send_command(follow_id, "Pause")
    #     time.sleep(0.5)
    #     send_command(follow_id, "Pause")
    #     time.sleep(0.5)

    follow_session.syncing = False
    db.session.commit()
    # print("UNPAUSING")
    # for i in range(2):
    #     send_command(follow_id, "Unpause")
    #     time.sleep(0.5)
    #     send_command(follow_id, "Unpause")
    #     time.sleep(0.5)

def set_playtime(session, time, item_id):
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
        return 0
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)

def send_command(session, command):
    url = '{0}/Sessions/{1}/Playing/{2}'.format(app.config['EMBY_SERVER'], session, command)
    if(command == 'Message'):
        url = '{0}/Sessions/{1}/Message'.format(app.config['EMBY_SERVER'], session)
        
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Token': app.config['SECRET_KEY'],
        
    }
    params = {
        'Text': 'Click "Got It" to Watch Together',
        'Header': 'Emby Sync'
    }
    response = requests.post(url, headers=headers,params=params)
    if response.status_code == 204:
        return 0
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)

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
