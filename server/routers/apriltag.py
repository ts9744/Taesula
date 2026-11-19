"""AprilTag API + 복귀 도착 시 홈 위치 확인.

  POST /apriltag/calibrate    로봇을 홈 칸 중앙에 정확히 놓고 한 번 누른다 (기준 저장, DB)
  GET  /apriltag/detect       지금 보이는 태그와 추정 위치
  POST /apriltag/home-check   홈 위치 다시 확인 (사람이 살짝 밀어 맞춘 뒤 누름)

복귀 도착(/command/done 에서 returned_home) -> after_return_home() 가 사진을 찍어 확인한다.
  - 기준이 없으면 확인하지 않는다 (태그를 안 쓰는 경우 기존 동작 그대로)
  - 어긋났거나 태그가 안 보이면 state.home_misaligned = True -> 대기열 출발/새 배송을 막는다
  - '시작점에 놓기' 또는 다시 확인이 통과하면 풀린다
"""
import json
import time

from fastapi import APIRouter, HTTPException

from server import state
from server.camera import apriltag as tagmod
from server.database import get_db, load_grid_from_db

router = APIRouter()

SETTLE_SEC = 0.3     # 브레이크 후 흔들림이 멎을 때까지 기다렸다가 찍는다


def capture():
    """카메라 프레임. 테스트에서 바꿔 끼울 수 있게 함수로 둔다."""
    from server.camera.camera import get_frame
    return get_frame()


# ---------- 기준값 저장 (DB) ----------
def _ensure_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS apriltag_ref (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL)")


def load_ref():
    conn = get_db()
    _ensure_table(conn)
    row = conn.execute("SELECT data FROM apriltag_ref WHERE id = 1").fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def save_ref(ref):
    conn = get_db()
    _ensure_table(conn)
    conn.execute("INSERT OR REPLACE INTO apriltag_ref (id, data) VALUES (1, ?)", (json.dumps(ref),))
    conn.commit()
    conn.close()


def _cols():
    grid = load_grid_from_db()
    return len(grid[0]) if grid else 0


def _home():
    from server.routers import home
    return home.load_home()


def _app(cell):
    """격자 좌표(0부터) -> 앱 좌표(1부터)"""
    return None if cell is None else [cell[0] + 1, cell[1] + 1]


def run_home_check(settle=True):
    """사진을 찍어 홈 위치를 확인하고 state 에 기록한다. 기준이 없으면 None."""
    ref = load_ref()
    if ref is None:
        return None
    home = _home()
    if home is None:
        return None
    if settle:
        time.sleep(SETTLE_SEC)
    try:
        frame = capture()
    except HTTPException as e:
        result = {"ok": False, "reason": "camera_error", "detail": e.detail, "error_cm": None, "located": None}
    else:
        result = tagmod.check_home(tagmod.detect_tags(frame), ref, home, _cols())
    result["home"] = _app(home)
    if result.get("located"):
        result["located"]["cell"] = _app(result["located"]["cell"])
    result["checked_at"] = time.time()
    with state.lock:
        state.home_check = result
        state.home_misaligned = not result["ok"]
    print(f"[apriltag] home check: {result['reason']} error_cm={result.get('error_cm')}", flush=True)
    return result


def after_return_home():
    """/command/done 이 홈 도착을 알린 직후 부른다 (state.lock 밖에서)."""
    return run_home_check(settle=True)


def clear_home_check():
    """'시작점에 놓기' 때 부른다."""
    state.home_check = None
    state.home_misaligned = False


# ---------- API ----------
@router.post("/apriltag/calibrate")
def calibrate():
    home, cols = _home(), _cols()
    if home is None or not cols:
        raise HTTPException(status_code=400, detail="격자 지도 또는 시작점이 없습니다.")
    tags = tagmod.detect_tags(capture())
    ref, err = tagmod.calibrate(tags, home, cols)
    if ref is None:
        raise HTTPException(status_code=400, detail=err)
    save_ref(ref)
    clear_home_check()
    return {"status": "calibrated", "ref": ref, "tags": [{"id": t["id"], "size_px": round(t["size_px"], 1)} for t in tags]}


@router.get("/apriltag/detect")
def detect():
    tags = tagmod.detect_tags(capture())
    ref, cols = load_ref(), _cols()
    loc = tagmod.locate(tags, ref, cols)
    if loc:
        loc["cell"] = _app(loc["cell"])
    return {
        "calibrated": ref is not None,
        "tags": [{k: t[k] for k in ("id", "cx", "cy", "size_px")} for t in tags],
        "located": loc,
    }


@router.post("/apriltag/home-check")
def home_check():
    if load_ref() is None:
        raise HTTPException(status_code=400, detail="기준이 없습니다. 로봇을 홈에 놓고 /apriltag/calibrate 를 먼저 하세요.")
    with state.lock:
        from server.routers import obstacle
        pos, home = obstacle._robot_pos(), _home()
        if pos is None or home is None or tuple(pos) != tuple(home) or state.current_path:
            raise HTTPException(status_code=409, detail="로봇이 홈에 멈춰 있을 때만 확인할 수 있습니다.")
    return run_home_check(settle=False)
