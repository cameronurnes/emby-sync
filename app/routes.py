import app
from flask import render_template, flash, redirect, url_for, request
from app import db
from app import app
from app.forms import *
from flask_login import current_user, login_user, logout_user, login_required
from app.models import User, Session
from werkzeug.urls import url_parse
from app.functions import *

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    update_or_create_sessions()
    sessions_blob = Session.query.all()
    room_list = [(i.room, i.room+get_room_leader(i.room)) for i in sessions_blob if i.room != None]
    room_list = list(set(room_list))
    form_list = [(i.session_id, i.device_name+" "+i.client_name+get_room_name(i)) for i in current_user.sessions if (i.is_stale == False) and (i.device_name != 'Emby Sync')]
    form = SessionList()
    form.room_selection.choices = room_list
    form.session_id.choices = form_list
    if form.validate_on_submit():
        if form.submit_room.data:
            if form.room_custom.data:
                room_choice = form.room_custom.data
            else:
                room_choice = form.room_selection.data
            for z in form.session_id.data:
                set_room(room_choice, z)
            flash('Room Set')
            return redirect(url_for('index'))
        if form.submit_leader.data:
            if len(form.session_id.data) >= 2:
                flash('Only one leader may be set')
                return redirect(url_for('index'))
            else:
                if form.room_custom.data:
                    room_choice = form.room_custom.data
                else:
                    room_choice = form.room_selection.data
                for z in form.session_id.data:
                    set_room(room_choice, z)
                    set_leader(room_choice, z)
                flash('Room and leader set')
                return redirect(url_for('index'))
        if form.submit_clear.data:
            for z in form.session_id.data:
                set_dead(z)
                session_cleanup()
            flash('Left room(s)')
            return redirect(url_for('index'))
        if form.submit_clear_all.data:
            for z in current_user.sessions:
                set_dead(z.session_id)
                session_cleanup()
            flash('Unsynced All')
            return redirect(url_for('index'))
    return render_template('index.html', title='Home', sessions=current_user.sessions, form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        authenticated, user = check_password(form.username.data, form.password.data)
        if not authenticated:
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        update_or_create_sessions()
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    end_session()
    logout_user()
    return redirect(url_for('login'))
