import sqlite3

conn = sqlite3.connect("warehouse.db")
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

conn.commit()
conn.close()

print("DB 생성 완료")