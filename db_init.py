import sqlite3

conn = sqlite3.connect("SIDA_system.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_name TEXT UNIQUE,
    x INTEGER,
    y INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    qr_code TEXT UNIQUE,
    destination_id INTEGER,
    status TEXT DEFAULT 'waiting',
    FOREIGN KEY(destination_id) REFERENCES locations(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS robot_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    current_x INTEGER DEFAULT 0,
    current_y INTEGER DEFAULT 0,
    status TEXT DEFAULT 'idle'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS grid_map (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    rows INTEGER NOT NULL,
    cols INTEGER NOT NULL,
    raw_grid TEXT NOT NULL,
    pathfinding_grid TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
INSERT OR IGNORE INTO robot_status (id, current_x, current_y, status)
VALUES (1, 0, 0, 'idle')
""")

conn.commit()
conn.close()