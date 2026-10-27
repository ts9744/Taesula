import sqlite3

from fastapi import APIRouter, HTTPException

from server.database import get_db


router = APIRouter()


# CREATE
@router.post("/items")
def create_item(name: str, qr_code: str, destination_id: int):
    conn = None

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 같은 이름의 item이 이미 있는지 확인
        cursor.execute(
            "SELECT id FROM items WHERE name=?",
            (name,)
        )
        duplicate_name = cursor.fetchone()

        if duplicate_name:
            raise HTTPException(
                status_code=400,
                detail="이미 같은 이름의 item이 존재합니다."
            )

        # 같은 qr_code의 item이 이미 있는지 확인
        cursor.execute(
            "SELECT id FROM items WHERE qr_code=?",
            (qr_code,)
        )
        duplicate_qr = cursor.fetchone()

        if duplicate_qr:
            raise HTTPException(
                status_code=400,
                detail="이미 같은 qr_code를 가진 item이 존재합니다."
            )

        cursor.execute(
            "INSERT INTO items (name, qr_code, destination_id) VALUES (?, ?, ?)",
            (name, qr_code, destination_id)
        )
        conn.commit()

        return {
            "message": "item created",
            "name": name,
            "qr_code": qr_code,
            "destination_id": destination_id
        }

    except sqlite3.OperationalError as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB 처리 중 오류가 발생했습니다: {e}"
        )

    finally:
        if conn:
            conn.close()


# READ ALL
@router.get("/items")
def get_items():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, qr_code, destination_id, status FROM items")
    rows = cursor.fetchall()

    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "qr_code": row[2],
            "destination_id": row[3],
            "status": row[4]
        }
        for row in rows
    ]


# READ (QR 기준)
@router.get("/items/{qr_code}")
def get_item(qr_code: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            items.id,
            items.name,
            items.qr_code,
            items.status,
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
            "status": row[3],
            "destination": {
                "location_id": row[4],
                "zone_name": row[5],
                "x": row[6],
                "y": row[7]
            }
        }

    return {"message": "not found"}


# UPDATE
@router.put("/items/{qr_code}")
def update_item(qr_code: str, name: str, destination_id: int):
    conn = None

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 수정 대상 item 존재 여부 확인
        cursor.execute(
            "SELECT id FROM items WHERE qr_code=?",
            (qr_code,)
        )
        target_item = cursor.fetchone()

        if not target_item:
            raise HTTPException(
                status_code=404,
                detail="수정할 item을 찾을 수 없습니다."
            )

        # 같은 이름을 가진 다른 item이 있는지 확인
        cursor.execute(
            "SELECT id FROM items WHERE name=? AND qr_code<>?",
            (name, qr_code)
        )
        duplicate_item = cursor.fetchone()

        if duplicate_item:
            raise HTTPException(
                status_code=400,
                detail="이미 같은 이름의 item이 존재합니다."
            )

        cursor.execute(
            "UPDATE items SET name=?, destination_id=? WHERE qr_code=?",
            (name, destination_id, qr_code)
        )

        conn.commit()

        return {
            "message": "item updated",
            "qr_code": qr_code,
            "name": name,
            "destination_id": destination_id
        }

    except sqlite3.OperationalError as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB 처리 중 오류가 발생했습니다: {e}"
        )

    finally:
        if conn:
            conn.close()


# DELETE
@router.delete("/items/{qr_code}")
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


# STATUS UPDATE
@router.put("/items/{qr_code}/status")
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
