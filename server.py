from fastapi import FastAPI
import sqlite3

app = FastAPI()

# DB 연결 함수
def get_db():
    return sqlite3.connect("warehouse.db")

# =========================
# ITEMS CRUD
# =========================

# CREATE
@app.post("/items")
def create_item(name: str, qr_code: str, destination_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO items (name, qr_code, destination_id) VALUES (?, ?, ?)",
        (name, qr_code, destination_id)
    )

    conn.commit()
    conn.close()

    return {"message": "item created"}

# READ ALL
@app.get("/items")
def get_items():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, qr_code, destination_id FROM items")
    rows = cursor.fetchall()

    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "qr_code": row[2],
            "destination_id": row[3]
        }
        for row in rows
    ]

# READ (QR 기준)
@app.get("/items/{qr_code}")
def get_item(qr_code: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            items.id,
            items.name,
            items.qr_code,
            locations.id,
            locations.zone_name,
            locations.x,
            locations.y
        FROM items
        JOIN locations
        ON items.destination_id = locations.id
        WHERE items.qr_code = ?
    """, (qr_code,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "item_id": row[0],
            "name": row[1],
            "qr_code": row[2],
            "destination": {
                "location_id": row[3],
                "zone_name": row[4],
                "x": row[5],
                "y": row[6]
            }
        }

    return {"message": "not found"}


# UPDATE
@app.put("/items/{qr_code}")
def update_item(qr_code: str, name: str, destination_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE items SET name=?, destination_id=? WHERE qr_code=?",
        (name, destination_id, qr_code)
    )

    conn.commit()
    conn.close()

    return {"message": "updated"}

# DELETE
@app.delete("/items/{qr_code}")
def delete_item(qr_code: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM items WHERE qr_code=?",
        (qr_code,)
    )

    conn.commit()
    conn.close()

    return {"message": "deleted"}


# =========================
# LOCATIONS
# =========================

@app.post("/locations")
def create_location(zone_name: str, x: int, y: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO locations (zone_name, x, y) VALUES (?, ?, ?)",
        (zone_name, x, y)
    )

    conn.commit()
    conn.close()

    return {"message": "location created"}

@app.get("/locations")
def get_locations():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, zone_name, x, y FROM locations")
    rows = cursor.fetchall()

    conn.close()

    return [
        {
            "id": row[0],
            "zone_name": row[1],
            "x": row[2],
            "y": row[3]
        }
        for row in rows
    ]

# =========================
# STATUS MANAGEMENT
# =========================

@app.put("/items/{qr_code}/status")
def update_item_status(qr_code: str, status: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE items SET status=? WHERE qr_code=?",
        (status, qr_code)
    )

    conn.commit()
    conn.close()

    return {
        "message": "item status updated",
        "qr_code": qr_code,
        "status": status
    }


@app.get("/robot/status")
def get_robot_status():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, current_x, current_y, status FROM robot_status")
    row = cursor.fetchone()

    conn.close()

    if row:
        return {
            "id": row[0],
            "current_x": row[1],
            "current_y": row[2],
            "status": row[3]
        }

    return {"message": "robot status not found"}


@app.put("/robot/status")
def update_robot_status(current_x: int, current_y: int, status: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM robot_status WHERE id=1")
    row = cursor.fetchone()

    if row:
        cursor.execute(
            "UPDATE robot_status SET current_x=?, current_y=?, status=? WHERE id=1",
            (current_x, current_y, status)
        )
    else:
        cursor.execute(
            "INSERT INTO robot_status (id, current_x, current_y, status) VALUES (1, ?, ?, ?)",
            (current_x, current_y, status)
        )

    conn.commit()
    conn.close()

    return {
        "message": "robot status updated",
        "current_x": current_x,
        "current_y": current_y,
        "status": status
    }