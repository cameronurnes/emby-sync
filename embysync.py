from app import app, db
from app.functions import check_password
from app.models import User, Session

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Session': Session, 'check_password': check_password}
