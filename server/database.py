import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "SIDA_system.db"


def get_db():
    return sqlite3.connect(DB_PATH)


def load_grid_from_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pathfinding_grid
        FROM grid_map
        WHERE id = 1
    """)

    row = cursor.fetchone()
    conn.close()

    if not row or row[0] is None:
        return None

    return json.loads(row[0])
