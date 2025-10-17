import os
os.environ['DISABLE_SQLITE_FALLBACK'] = '1'
from app import app
from sqlalchemy import text

with app.app_context():
    db = app.extensions['sqlalchemy'].db
    rows = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'fds_reports' ORDER BY column_name"))
    print([row[0] for row in rows])
