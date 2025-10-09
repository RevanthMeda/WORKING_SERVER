from app import app, db
from sqlalchemy import inspect

with app.app_context():
    insp = inspect(db.engine)
    for col in insp.get_columns("api_keys"):
        print(f"{col['name']}: {col['type']}")
