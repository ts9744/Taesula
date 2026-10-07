import sqlite3

from fastapi import APIRouter, HTTPException

from server.database import get_db


router = APIRouter()


@router.post("/locations")
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


@router.get("/locations")
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


@router.put("/locations/{location_id}")
def update_location(location_id: int, zone_name: str, x: int, y: int):
    conn = None

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 수정 대상 location 존재 여부 확인
        cursor.execute(
            "SELECT id FROM locations WHERE id=?",
            (location_id,)
        )
        target_location = cursor.fetchone()

        if not target_location:
            raise HTTPException(
                status_code=404,
                detail="수정할 location을 찾을 수 없습니다."
            )

        # 같은 이름을 가진 다른 location이 있는지 확인
        cursor.execute(
            "SELECT id FROM locations WHERE zone_name=? AND id<>?",
            (zone_name, location_id)
        )
        duplicate_location = cursor.fetchone()

        if duplicate_location:
            raise HTTPException(
                status_code=400,
                detail="이미 같은 이름의 location이 존재합니다."
            )

        cursor.execute(
            "UPDATE locations SET zone_name=?, x=?, y=? WHERE id=?",
            (zone_name, x, y, location_id)
        )

        conn.commit()

        return {
            "message": "location updated",
            "id": location_id,
            "zone_name": zone_name,
            "x": x,
            "y": y
        }

    except sqlite3.OperationalError as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB 처리 중 오류가 발생했습니다: {e}"
        )

    finally:
        if conn:
            conn.close()


@router.delete("/locations/{location_id}")
def delete_location(location_id: int):
    conn = None

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 삭제 대상 location 존재 여부 확인
        cursor.execute(
            "SELECT id FROM locations WHERE id=?",
            (location_id,)
        )
        target_location = cursor.fetchone()

        if not target_location:
            raise HTTPException(
                status_code=404,
                detail="삭제할 location을 찾을 수 없습니다."
            )

        # 해당 location을 목적지로 사용하는 item이 있는지 확인
        cursor.execute(
            "SELECT id FROM items WHERE destination_id=?",
            (location_id,)
        )
        linked_item = cursor.fetchone()

        if linked_item:
            raise HTTPException(
                status_code=400,
                detail="해당 location을 목적지로 사용하는 item이 있어 삭제할 수 없습니다."
            )

        cursor.execute(
            "DELETE FROM locations WHERE id=?",
            (location_id,)
        )

        conn.commit()

        return {
            "message": "location deleted",
            "id": location_id
        }

    except sqlite3.OperationalError as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB 처리 중 오류가 발생했습니다: {e}"
        )

    finally:
        if conn:
            conn.close()
