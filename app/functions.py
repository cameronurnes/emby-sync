import app
import datetime
import random
import platform
import requests
import json
import string
import threading
import time
from app import INTERVAL, app
from app import db
from app import functions
from app.models import Session
from app.models import User
from app.models import Room
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

## Broken
# def addAllUsers():
#     responses = getSessionJson()
#     printJsonResponce(responses)
#     for response in responses:
#         user = db.session.query(User).filter_by(username=response['User']['Name'].lower()).first()
#         ## If the user cannot be found in the database, add it
#         if(not user):
#             newuser = User(emby_id=response['User']['Id'], username=response['User']['Name'].lower(), access_key=response['AccessToken'], device_id=response['SessionInfo']['DeviceId'])
#             db.session.add(newuser)
#             db.session.commit()

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
        'X-Emby-Device-Name': 'Emby Sync'
        # 'X-Emby-Token': current_user.access_key
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
            pass

    response_json = getSessionJson()

    newlastTimeUpdatedAt = datetime.datetime.now()
    active_users = []
    for z in response_json:
        try:
            emby_session = db.session.query(Session).filter_by(session_id=z['Id']).first()
            date_time_obj = datetime.datetime.fromisoformat(z['LastActivityDate'][:-2])
            ip_obj = z['RemoteEndPoint']
            # if stale_calc(date_time_obj, 300):
            #     pass
            if emby_session:
                emby_session.timestamp = date_time_obj
                emby_session.ip_address = ip_obj
                if(emby_session.loading == False):
                    ## Do nothing as nothing has changed in the user
                    if('NowPlayingItem' in z):
                        if(emby_session.playing == True and 
                            emby_session.item_id == int(z['NowPlayingItem']['Id']) and 
                            emby_session.ticks == z['PlayState']['PositionTicks'] and 
                            emby_session.is_paused == z['PlayState']['IsPaused']):
                            pass
                        else:
                            emby_session.playing = True
                            emby_session.item_id = z['NowPlayingItem']['Id']
                            emby_session.ticks = z['PlayState']['PositionTicks']
                            emby_session.is_paused = z['PlayState']['IsPaused']
                            emby_session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                            if(emby_session.room_id):
                                room = db.session.query(Room).filter_by(id=emby_session.room_id).first()
                                if(room.playing == False):
                                    print('Setting room with brand new play')
                                    room.playing = True
                                    room.item_id = z['NowPlayingItem']['Id']
                                    room.ticks = z['PlayState']['PositionTicks']
                                    room.is_paused = z['PlayState']['IsPaused']
                                    room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    else:
                        ## Do nothing as nothing has changed in the user
                        if(emby_session.playing == False and 
                            emby_session.item_id == None and 
                            emby_session.ticks == None and 
                            emby_session.is_paused == z['PlayState']['IsPaused']):
                            pass
                        else:
                            emby_session.playing = False
                            emby_session.item_id = None
                            emby_session.ticks = None
                            emby_session.is_paused = z['PlayState']['IsPaused']
                            emby_session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                else:
                    print('happened')
            else:
                if z['DeviceId'] != 'session-sync':
                    print("new session user")
                    newsession = Session(user_id=z['UserId'], session_id=z['Id'], device_name=z['DeviceName'], timestamp=date_time_obj, client_name=z['Client'], device_id=z['DeviceId'], ip_address=ip_obj)
                    db.session.add(newsession)
                else:
                    newsession = Session(session_id=z['Id'], device_name=z['DeviceName'], timestamp=date_time_obj, client_name=z['Client'], device_id=z['DeviceId'], ip_address=ip_obj)
                    db.session.add(newsession)

            db.session.commit()
            active_users.append(z['Id'])

        except KeyError:
            print(KeyError)
            pass
    
    return active_users

def set_leader(room_name, emby_session_id):
    print("set_leader")
    emby_session = db.session.query(Session).filter_by(room=room_name, leader=True).first()
    if emby_session:
        emby_session.leader = False
        db.session.commit()
        emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
        emby_session.room = room_name
        emby_session.leader = True
        db.session.commit()
    return True

def create_room(room_name):
    print("creating new room")
    current_time = datetime.datetime.now()
    new_room = Room(roomname=room_name,lastTimeUpdatedAt=current_time)
    db.session.add(new_room)
    db.session.commit()

def set_room(room_name, emby_session_id):
    room = db.session.query(Room).filter_by(roomname=room_name).first()
    if(not room):
        create_room(room_name)
    emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
    room = db.session.query(Room).filter_by(roomname=room_name).first()
    emby_session.room_id = room.id
    emby_session.syncing = True
    emby_session.loading = False
    emby_session.lastTimeUpdatedAt = datetime.datetime.now()
    db.session.commit()
    
    ## if room is playing, set newly joined to session stuff
        
    ## For when a new person joins that isn't the leader
    if(emby_session.device_id != 'session-sync'):
        send_command(emby_session.session_id, "Message")

    ## No leader exists
    # else:
    #     emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
    #     emby_session.room = room_name
    #     if (emby_session.device_name != 'Emby Sync'):
    #         emby_session.leader = True
    #     db.session.commit()
    return True

# def set_room(room_name, emby_session_id):
#     emby_session = db.session.query(Session).filter_by(room=room_name, leader=True).first()
#     if emby_session:
#         emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
#         emby_session.room = room_name
#         emby_session.leader = False
#         db.session.commit()

#         ## For when a new person joins that isn't the leader
#         if(emby_session.device_id != 'session-sync'):
#             send_command(emby_session.session_id, "Message")

#     ## No leader exists
#     else:
#         emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
#         emby_session.room = room_name
#         if (emby_session.device_name != 'Emby Sync'):
#             emby_session.leader = True
#         db.session.commit()
#     return True

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

def sendRoomCommand(room, active_room_sessions, command):
    print(f'Issuing command: {command} for room: {room.roomname}')
    newlastTimeUpdatedAt = room.lastTimeUpdatedAt
    for session in active_room_sessions:
        send_command(session.session_id,command)
        session.lastTimeUpdatedAt = newlastTimeUpdatedAt
    db.session.commit()

def updateRoom(room, active_room_sessions):
    # print(f'Updating information for room: {room.roomname}')

    newlastTimeUpdatedAt = datetime.datetime.now()
    checkForAnyUserPlaying = False
    for session in active_room_sessions:
        # print(f'room:    {room.lastTimeUpdatedAt}')
        # print(f'session: {session.lastTimeUpdatedAt}')
        if(session.syncing == True):
            ## This is to set a session to no longer get synced as it has left the video currently playing
            if((room.playing == True and session.playing == False) and room.lastTimeUpdatedAt <= session.lastTimeUpdatedAt):
                print('session no longer in sync')
                session.syncing = False
                session.lastTimeUpdatedAt = newlastTimeUpdatedAt
            elif((room.playing == True and session.playing == True) and (room.is_paused == False and session.is_paused == True) and (room.lastTimeUpdatedAt <= session.lastTimeUpdatedAt)):
                print('Pausing room')
                room.is_paused = True
                room.ticks = session.ticks
                room.lastTimeUpdatedAt = newlastTimeUpdatedAt
            elif((room.playing == True and session.playing == True) and (room.is_paused == True and session.is_paused == False) and (room.item_id == session.item_id) and (room.lastTimeUpdatedAt <= session.lastTimeUpdatedAt)):
                print('Resuming room')
                room.is_paused = False
                room.ticks = session.ticks
                room.lastTimeUpdatedAt = newlastTimeUpdatedAt
            elif((room.playing == True and session.playing == True) and (session.ticks != 0 and room.item_id == session.item_id) and (room.lastTimeUpdatedAt <= session.lastTimeUpdatedAt)):
                sync_drift = check_sync(session.ticks, room.ticks)
                # print(f'sync: {sync_drift}')
                localTime = session.lastTimeUpdatedAt - datetime.timedelta(seconds=sync_drift)
                # print(f'session update: {session.lastTimeUpdatedAt}')
                # print(f'local: {localTime}')
                # print(f'room update: {room.lastTimeUpdatedAt}')
                # print(f'server: {serverTime}')
                timeDifference = localTime - room.lastTimeUpdatedAt
                # print(f'diff: {timeDifference.total_seconds()}')
                if(abs(timeDifference.total_seconds()) >= 10):
                    print('Time difference, updating server and pausing room')
                    room.is_paused = True
                    room.ticks = session.ticks
                    room.lastTimeUpdatedAt = newlastTimeUpdatedAt
        else:
            ## This is for when a session start playing a different video from the room, this will update the room
            if(room.playing == True and session.playing == True and room.item_id != session.item_id):
                print('A user has started a different video while another one was playing')
                room.item_id = session.item_id
                room.ticks = session.ticks
                room.is_paused = session.is_paused
                room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                session.syncing = True
                session.lastTimeUpdatedAt = newlastTimeUpdatedAt

        ## This is used to see if any user is actually currently watching something, else set the
        ## the room state to nothing
        if(session.playing == True and checkForAnyUserPlaying == False):
            checkForAnyUserPlaying = True

        db.session.commit()

    ## No user is playing anything, set room state to nothing
    if(not checkForAnyUserPlaying and room.playing != False):
        print('No user was playing anything, setting room to nothing')
        room.playing = False
        room.item_id = None
        room.ticks = None
        room.is_paused = True
        for session in active_room_sessions:
            session.syncing = True
        room.lastTimeUpdatedAt = newlastTimeUpdatedAt
        
    db.session.commit()

def sync_cycle():
    print('==========================================================')
    start = time.time()
    active_users = update_or_create_sessions()
    full_session_list = Session.query.all()
    ## This will only get the users that are actually connected to the Emby server
    active_session_list = [session for session in full_session_list if(session.session_id in active_users)]
    
    rooms = Room.query.all()
    for room in rooms:
        # sessions = Session.query.filter(Session.room_id == room.id, Session.device_id != 'session-sync').all()
        sessions = [session for session in active_session_list if(session.room_id == room.id and session.device_id != 'session-sync')]
        updateRoom(room,sessions)
        # print(sessions)
        newlastTimeUpdatedAt = datetime.datetime.now()
        for session in sessions:
            if(session.syncing == True):
                # print(f'{room.is_paused} - {room.playing}')
                # print(f'{session.is_paused} - {session.playing}')
                ## If the room is currently has a video playing and the user doesn't
                ## Or if the room and user doesn't have the same video playing
                if((room.playing == True) and (session.playing == False or room.item_id != session.item_id) and (session.ticks != 0)):
                    print("FOLLOWER NEEDS TO START PLAYING")
                    room.is_paused = True
                    room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.syncing = False
                    session.is_paused = True
                    db.session.commit()
                    # send_command(session.session_id,'Pause')
                    sendRoomCommand(room,sessions,'Pause')
                    app.apscheduler.add_job(func=sync, trigger='date', args=[room.ticks,room.item_id,session.session_id,session], id="Sync "+session.session_id)    
                ## 
                if((room.playing == True and session.playing == True) and (room.is_paused == True and session.is_paused == False)):
                    print("Pausing all followers")
                    room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    db.session.commit()
                    send_command(session.session_id,'Pause')
                    # sendRoomCommand(room,sessions,'Pause')
                ##
                if((room.playing == True and session.playing == True) and (room.is_paused == False and session.is_paused == True)):
                    print("Resuming all followers")
                    room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    db.session.commit()
                    send_command(session.session_id,'Unpause')
                    # while(True):
                    #     if(session.lastTimeUpdatedAt > newlastTimeUpdatedAt):
                    #         session.syncing = True
                    #         db.session.commit()
                    #         break
                    # sendRoomCommand(room,sessions,'Unpause')
                if((room.playing == True and session.playing == True) and (session.ticks != 0)):
                    sync_drift = check_sync(session.ticks, room.ticks)
                    localTime = session.lastTimeUpdatedAt - datetime.timedelta(seconds=sync_drift)
                    timeDifference = localTime - room.lastTimeUpdatedAt
                    if(abs(timeDifference.total_seconds()) >= 10):
                        print('Follower out of sync, syncing with room')
                        room.is_paused = True
                        room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                        session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                        session.syncing = False
                        session.is_paused = True
                        session.loading = True
                        db.session.commit()
                        send_command(session.session_id,'Pause')
                        # sendRoomCommand(room,sessions,'Pause')
                        app.apscheduler.add_job(func=syncTicks, trigger='date', args=[room.ticks,room.lastTimeUpdatedAt,session.session_id,session], id="Sync "+session.session_id)     
    
    end = time.time()
    # print(f'Round trip: {end - start}')

# def sync_cycle():
#     start = time.time()
#     active_users = update_or_create_sessions()
#     full_session_list = Session.query.all()
#     ## This will only get the users that are actually connected to the Emby server
#     active_session_list = [session for session in full_session_list if(session.session_id in active_users)]
#     rooms = Room.query.all()
#     for room in rooms:
#         # sessions = Session.query.filter(Session.room_id == room.id, Session.device_id != 'session-sync').all()
#         sessions = [session for session in active_session_list if(session.room_id == room.id and session.device_id != 'session-sync')]
#         updateRoom(room,sessions)
#         # print(sessions)
#         newlastTimeUpdatedAt = datetime.datetime.now()
#         for session in sessions:
#             if(session.syncing == True):
#                 if((room.playing == True and session.playing == True)):
#                     sync_drift = check_sync(session.ticks, room.ticks)
#                     localTime = session.lastTimeUpdatedAt - datetime.timedelta(seconds=sync_drift)
#                     timeDifference = datetime.timedelta(seconds=sync_drift) if room.is_paused else (localTime - room.lastTimeUpdatedAt)
#                     if((abs(timeDifference.total_seconds()) >= 10) and (session.ticks != 0)):
#                         print(abs(timeDifference.total_seconds()))
#                         print(f'room:    {room.ticks}')
#                         print(f'session: {session.ticks}')
#                         print('Follower out of sync, syncing with room')
#                         room.is_paused = True
#                         room.lastTimeUpdatedAt = newlastTimeUpdatedAt
#                         session.syncing = False
#                         session.is_paused = True
#                         db.session.commit()
#                         send_command(session.session_id,'Pause')
#                         # sendRoomCommand(room,sessions,'Pause')
#                         app.apscheduler.add_job(func=syncTicks, trigger='date', args=[room.ticks,session.session_id,session], id="Sync "+session.session_id)                   
#                     ## 
#                     elif((room.is_paused == True and session.is_paused == False)):
#                         print("Pausing all followers")
#                         room.lastTimeUpdatedAt = newlastTimeUpdatedAt
#                         db.session.commit()
#                         send_command(session.session_id,'Pause')
#                         # sendRoomCommand(room,sessions,'Pause')
#                     ##
#                     elif((room.is_paused == False and session.is_paused == True)):
#                         print("Resuming all followers")
#                         room.lastTimeUpdatedAt = newlastTimeUpdatedAt
#                         db.session.commit()
#                         send_command(session.session_id,'Unpause')
#                         # sendRoomCommand(room,sessions,'Unpause')
#                 ## If the room is currently has a video playing and the user doesn't
#                 ## Or if the room and user doesn't have the same video playing
#                 elif((room.playing == True) and (session.playing == False or room.item_id != session.item_id) and (session.ticks != 0)):
#                     print("FOLLOWER NEEDS TO START PLAYING")
#                     room.is_paused = True
#                     room.lastTimeUpdatedAt = newlastTimeUpdatedAt
#                     session.syncing = False
#                     session.is_paused = True
#                     db.session.commit()
#                     sendRoomCommand(room,sessions,'Pause')
#                     app.apscheduler.add_job(func=sync, trigger='date', args=[room.ticks,room.item_id,session.session_id,session], id="Sync "+session.session_id)    
    
#     end = time.time()
#     # print(f'Round trip: {end - start}')


            
# def sync_cycle():
#     active_users = update_or_create_sessions()
#     full_session_list = Session.query.all()
    # active_session_list = [session for session in full_session_list if(session.session_id in active_users)]

    # for z in active_session_list:
    #     # stale_check(z)

    #     ## This is just for the leader/emby-sync, so nothing happens
    #     if(z.device_id == 'session-sync'):
    #         pass
    #     # if (z.leader == True) or (z.device_id == 'session-sync'):
    #     #     pass
    #     ## This is just for the followers
    #     else:
    #         if (z.room != None) and (z.is_stale == False):
    #             leader_session = db.session.query(Session).filter_by(room=z.room, leader=True).first()
    #             # session_user = db.session.query(User).filter_by(emby_id=z.user_id).first()
                    
    #             if leader_session:

    #                 ## Leader are Follower are not currently in any video
    #                 if(leader_session.playing == False) and (z.playing == False):
    #                     pass
    #                 ## This is for when the follower tries to start playing when synced to a room. This forces the follower to follow the leader
    #                 if(leader_session.playing == False) and (z.playing == True):
    #                     print("STOP")
    #                     send_command(z.session_id, "Stop")
    #                     z.syncing = False
    #                     db.session.commit()
    #                 ## This is for when the leader pauses and forces the follower to pause
    #                 if(leader_session.playing == True) and (leader_session.is_paused == True) and (z.playing == True) and (z.is_paused == False):
    #                     print("PAUSE")
    #                     send_command(z.session_id, "Pause")
    #                     z.syncing = False
    #                     db.session.commit()
    #                 ## This if for when the leader resumes from a paused state
    #                 if(leader_session.playing == True) and (leader_session.is_paused == False) and (z.playing == True) and (z.is_paused == True) and (z.syncing == False):
    #                     print("RESUME")
    #                     send_command(z.session_id, "Unpause")
    #                     z.syncing = True
    #                     db.session.commit()
    #                 ## This if for when the leader starts playing and the follower is does not have any video loaded
    #                 if(leader_session.playing == True) and (leader_session.is_paused == False) and (z.playing == False) and (leader_session.ticks != 0):
    #                     print("FOLLOWER NEEDS TO START PLAYING")
    #                     send_command(leader_session.session_id,"Pause")
    #                     app.apscheduler.add_job(func=sync, trigger='date', args=[z, z.session_id, leader_session.session_id, leader_session.ticks, leader_session.item_id], id="Sync "+z.session_id+" "+leader_session.session_id)
    #                     z.syncing = True
    #                     db.session.commit()
    #                 if(leader_session.playing == True) and (z.playing == True) and (leader_session.ticks != 0):
    #                     sync_drift = check_sync(z.ticks, leader_session.ticks)
    #                     print(f"Follower: {z.user_id} {z.device_name} drift: {sync_drift}")
    #                     if abs(sync_drift) >= 10:
    #                         app.apscheduler.add_job(func=sync, trigger='date', args=[z, z.session_id, leader_session.session_id, leader_session.ticks, leader_session.item_id], id="Sync "+z.session_id+" "+leader_session.session_id)
    #                         z.syncing = True
    #                         db.session.commit()
    
def check_sync(session_ticks, room_ticks):
    drift = (session_ticks/10000000) - (room_ticks/10000000)
    return drift

def sync(room_ticks, room_item, follow_session_id, follow_session):
    target = room_ticks + int(INTERVAL*10000000) # Load x seconds ahead to give user time to buffer
    set_playtime(follow_session_id, target, room_item)

    ## This is a do-while loop
    while(True):
        send_command(follow_session_id, "Pause")
        time.sleep(0.3)
        with app.app_context():
            follow_session = db.session.query(Session).filter_by(session_id=follow_session_id).first()
            if(follow_session.ticks != None and (follow_session.ticks >= target or follow_session.ticks == 0) and (follow_session.is_paused == True and follow_session.item_id == room_item)):
                follow_session.syncing = True
                print('Session is now synced with server')
                db.session.commit()
                break

def syncTicks(room_ticks, room_lastTimeUpdatedAt, follow_session_id, follow_session):
    target = room_ticks + int(INTERVAL*10000000) # Load x seconds ahead to give user time to buffer
    setTickPosition(follow_session_id, target)
    with app.app_context():
        follow_session = db.session.query(Session).filter_by(session_id=follow_session_id).first()
        follow_session.loading = False
        db.session.commit()
    
    # time.sleep(INTERVAL/2)
    ## This is a do-while loop
    while(True):
        with app.app_context():
            follow_session = db.session.query(Session).filter_by(session_id=follow_session_id).first()
            if(follow_session.ticks != None and (follow_session.ticks == target or follow_session.ticks == 0) and follow_session.lastTimeUpdatedAt > room_lastTimeUpdatedAt):
                follow_session.syncing = True
                db.session.commit()
                print('Session is now synced with server')
                break
    

# def sync(follow_session, follow_id, leader_session, leader_ticks, leader_item):
#     target = leader_ticks + (3*10000000) # Load 3 seconds ahead to give user time to buffer
#     set_playtime(follow_id, target, leader_item)

#     print("PAUSING")
#     end = time.time() + 3 ## Adding 3 seconds to the current time
#     while((time.time() < end) or (follow_session.ticks == None)):
#         send_command(follow_id, "Pause")
#         time.sleep(0.5)
#         send_command(follow_id, "Pause")
#         time.sleep(0.5)

#     # for i in range(8):
#     #     send_command(follow_id, "Pause")
#     #     time.sleep(0.5)
#     #     send_command(follow_id, "Pause")
#     #     time.sleep(0.5)

#     follow_session.syncing = False
#     db.session.commit()
#     # print("UNPAUSING")
#     # for i in range(2):
#     #     send_command(follow_id, "Unpause")
#     #     time.sleep(0.5)
#     #     send_command(follow_id, "Unpause")
#     #     time.sleep(0.5)

def setTickPosition(session, ticks):
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
        'SeekPositionTicks': ticks
    }
    response = requests.post(url, headers=headers, params=params)
    if response.status_code == 204:
        return 0
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)

def set_playtime(session, ticks, item_id):
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
        'StartPositionTicks': ticks
    }
    response = requests.post(url, headers=headers, params=params)
    if response.status_code == 204:
        return 0
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)

## Change the param from taking just the session id to the full session
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
        'X-Emby-Token': app.config['SECRET_KEY']
    }
    params = {
        'Text': 'Click "Got It" to Watch Together',
        'Header': '&emsp;&emsp;Emby - Sync&emsp;&emsp;'
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
        # leader_user = db.session.query(User).filter_by(emby_id=leader_session.user_id).first()
        # return "  --  Current leader is {0}".format(leader_user.username)
        return "  --  Current leader is "

    else:
        return ""

def get_room_name(session):
    room = db.session.query(Room).filter_by(id=session.room_id).first()
    if(room):
        return f' -- Synced to {room.roomname}'
    return ' -- Not Synced'

    # if session.room and session.leader != True:
    #     return " -- Synced to {0}".format(session.room)
    # if session.room and session.leader == True:
    #     return " -- Leading {0}".format(session.room)
    # else:
    #     return " -- Not Synced"
