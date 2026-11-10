from flask import g
import os
import shutil
import sqlite3

PROJECT_DB = os.path.join(os.path.abspath(os.path.dirname(__file__)), "app.db")

# On Vercel the project folder is read-only, so SQLite can't save changes there.
# Copy the database into /tmp (the only writable folder) and use that copy.
# Note: Vercel can throw /tmp away at any time, so changes there are temporary.
if os.environ.get("VERCEL"):
    DATABASE = "/tmp/app.db"
    if not os.path.exists(DATABASE) and os.path.exists(PROJECT_DB):
        shutil.copyfile(PROJECT_DB, DATABASE)
else:
    DATABASE = PROJECT_DB

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

# Adds columns that newer code needs to an older app.db, so nobody has to
# rebuild their database by hand. Safe to run every time the app starts.
def ensure_schema():
    if not os.path.exists(DATABASE):
        return
    db = sqlite3.connect(DATABASE)
    columns = [row[1] for row in db.execute("PRAGMA table_info(flights);")]
    if columns and "approved" not in columns:
        db.execute("ALTER TABLE flights ADD COLUMN approved INTEGER NOT NULL DEFAULT 0;")
        db.commit()
    db.close()
