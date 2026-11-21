"""AprilTag API + 복귀 도착 시 홈 위치 확인 + 짧은 이동(nudge)으로 자동 보정.

  POST /apriltag/calibrate      로봇을 홈 칸 중앙에 정확히 놓고 한 번 누른다 (기준 저장, DB) [관리자]
  GET  /apriltag/detect         지금 보이는 태그와 추정 위치
  POST /apriltag/home-check     홈 위치 다시 확인 (어긋났으면 자동 보정 시작)
  POST /apriltag/measure-moves  홈에서 1칸 이동/짧은 이동/회전을 해 보고 실제 이동 거리를 잰다 [관리자]
                                -> PULSES_PER_CM_FWD / PULSES_PER_CM_STRAFE 추천값 + 짧은 이동 배율 학습
  GET  /apriltag/status         진행 중인 작업, 마지막 결과, 학습된 짧은 이동 모델
  POST /apriltag/job-done       브리지가 raw 명령(nudge 등)을 끝낼 때마다 부른다

흐름
  - 복귀 도착(/command/done 의 returned_home) -> after_return_home() 가 사진을 찍어 확인
  - 어긋났으면(5cm / 3도 초과) 자동 보정: 가장 큰 오차 하나를 nudge 로 줄이고 -> 다시 찍고 -> 반복
  - ESP32(feat-robot 펌웨어)는 엔코더 펄스로 거리를 센다. 짧은 이동은 cm, 회전은 도 단위로 보낸다.
      nudge <forward|backward|left|right> <cm>   (1~15cm, 응답: DONE nudge <방향> <cm>)
      rotate <각도>                              (+ 시계 / - 반시계, 응답: DONE rotate <각도>)
  - 명령한 양과 AprilTag 로 잰 실제 이동량을 DB 에 쌓아 '실제/명령' 배율을 맞춘다 (쓸수록 정확해짐)
  - 보정이 안 되면(MAX_STEPS 초과, 오차가 너무 큼, 태그가 안 보임, ESP32 가 거부) 사람을 부른다
  - 그동안 state.home_misaligned = True 라 대기열 출발/새 배송은 멈춰 있다

명령 전달: state.current_path 에 "raw:<ESP32 로 보낼 줄>" 을 넣는다.
  /next-command 가 {"direction": "raw", "line", "expect"} 로 내보내고, 브리지는 그대로 보내고 결과를 job-done 으로 알린다.
  raw 명령은 DB 위치를 바꾸지 않는다 (같은 칸 안에서의 보정이므로).
"""
import json
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server import state
from server.admin import require_admin
from server.camera import apriltag as tagmod
from server.database import get_db, load_grid_from_db

router = APIRouter()

SETTLE_SEC = 0.3     # 브레이크 후 흔들림이 멎을 때까지 기다렸다가 찍는다

# ---------- 자동 보정 설정 ----------
AUTO_CORRECT = True
AUTO_MAX_CM = 20.0       # 이보다 크게 어긋났으면 자동 보정하지 않고 사람을 부른다
AUTO_MAX_DEG = 15.0
TARGET_CM = 2.5          # 보정할 때 이 이하로 줄이려고 한다 (끝내는 기준은 HOME_TOL_CM)
MAX_STEPS = 8            # nudge 최대 횟수
GAIN = 0.9               # 계산한 양의 90% 만 보낸다 (지나치지 않게)

GROUP = {"forward": "fb", "backward": "fb", "left": "lr", "right": "lr", "cw": "rot", "ccw": "rot"}
UNIT = {"fb": "cm", "lr": "cm", "rot": "deg"}
# 펌웨어 범위 (feat-robot main.cpp): nudge 1~15cm, rotate 최대 ROTATE_MAX_DEG(180)
# 범위를 넘는 값을 보내면 펌웨어가 잘라서 응답하므로 expect("DONE <line>") 와 달라진다 -> 여기서 미리 자른다
CMD_MIN = {"fb": 1, "lr": 1, "rot": 1}
CMD_MAX = {"fb": 15, "lr": 15, "rot": 30}
MIN_SCALE, MAX_SCALE = 0.3, 3.0                 # 배율이 이 밖이면 측정이 잘못된 것으로 보고 무시
MAX_SAMPLES = 30


def capture():
    """카메라 프레임. 테스트에서 바꿔 끼울 수 있게 함수로 둔다."""
    from server.camera.camera import get_frame
    return get_frame()


# ---------- DB ----------
def _ensure_tables(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS apriltag_ref (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL)")
    # 예전 nudge_samples(ms 기준)는 엔코더 펌웨어와 단위가 달라 쓰지 않는다
    conn.execute("""CREATE TABLE IF NOT EXISTS nudge_samples_enc (
        id INTEGER PRIMARY KEY AUTOINCREMENT, grp TEXT NOT NULL, cmd REAL NOT NULL,
        delta REAL NOT NULL, ts REAL NOT NULL)""")


def load_ref():
    conn = get_db()
    _ensure_tables(conn)
    row = conn.execute("SELECT data FROM apriltag_ref WHERE id = 1").fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def save_ref(ref):
    conn = get_db()
    _ensure_tables(conn)
    conn.execute("INSERT OR REPLACE INTO apriltag_ref (id, data) VALUES (1, ?)", (json.dumps(ref),))
    conn.commit()
    conn.close()


def add_sample(grp, cmd, delta):
    """cmd: 명령한 양(cm 또는 도), delta: AprilTag 로 잰 실제 이동량"""
    conn = get_db()
    _ensure_tables(conn)
    conn.execute("INSERT INTO nudge_samples_enc (grp, cmd, delta, ts) VALUES (?, ?, ?, ?)",
                 (grp, float(cmd), float(delta), time.time()))
    conn.execute("""DELETE FROM nudge_samples_enc WHERE grp = ? AND id NOT IN
                    (SELECT id FROM nudge_samples_enc WHERE grp = ? ORDER BY id DESC LIMIT ?)""", (grp, grp, MAX_SAMPLES))
    conn.commit()
    conn.close()


def clear_samples():
    conn = get_db()
    _ensure_tables(conn)
    conn.execute("DELETE FROM nudge_samples_enc")
    conn.commit()
    conn.close()


def nudge_model(grp):
    """쌓인 샘플로 '실제 이동량 = scale * 명령한 양' 의 scale 을 맞춘다 (원점 지나는 직선). 샘플이 없으면 None."""
    conn = get_db()
    _ensure_tables(conn)
    rows = conn.execute("SELECT cmd, delta FROM nudge_samples_enc WHERE grp = ?", (grp,)).fetchall()
    conn.close()
    rows = [(c, d) for c, d in rows if c > 0 and MIN_SCALE <= d / c <= MAX_SCALE]
    if not rows:
        return None
    scale = sum(c * d for c, d in rows) / sum(c * c for c, _ in rows)
    return {"scale": scale, "n": len(rows)}


def plan_amount(grp, want):
    """want(cm 또는 도)만큼 움직이려면 펌웨어에 얼마를 보낼지. 정수, 펌웨어 범위 안."""
    m = nudge_model(grp)
    scale = m["scale"] if m else 1.0          # 학습 전에는 펌웨어 엔코더 값을 그대로 믿는다
    amt = round(GAIN * want / scale)
    return int(min(max(amt, CMD_MIN[grp]), CMD_MAX[grp]))


def _cmd_line(d, amount):
    """방향 + 양 -> ESP32 로 보낼 한 줄"""
    if d == "cw":
        return f"rotate {amount}"
    if d == "ccw":
        return f"rotate -{amount}"
    return f"nudge {d} {amount}"


def _parse_line(line):
    """ESP32 명령 한 줄 -> (방향, 양). 1칸 이동(forward 1 등)은 양 = 칸 수."""
    parts = line.split()
    if parts[0] == "nudge":
        return parts[1], int(parts[2])
    if parts[0] == "rotate":
        deg = int(parts[1])
        return ("cw" if deg > 0 else "ccw"), abs(deg)
    return parts[0], int(parts[1])


# ---------- 공통 ----------
def _cols():
    grid = load_grid_from_db()
    return len(grid[0]) if grid else 0


def _home():
    from server.routers import home
    return home.load_home()


def _app(cell):
    """격자 좌표(0부터) -> 앱 좌표(1부터)"""
    return None if cell is None else [cell[0] + 1, cell[1] + 1]


def _measure(settle=True):
    """사진 한 장으로 홈 확인 결과를 만든다 (lock 밖에서 부른다). 기준이 없으면 None."""
    ref, home = load_ref(), _home()
    if ref is None or home is None:
        return None
    if settle:
        time.sleep(SETTLE_SEC)
    try:
        frame = capture()
    except HTTPException as e:
        return {"ok": False, "reason": "camera_error", "detail": e.detail, "error_cm": None,
                "yaw_deg": None, "located": None, "home": _app(home)}
    if not _same_frame(ref, frame):
        return {"ok": False, "reason": "recalibrate", "detail": _frame_msg(ref, frame), "error_cm": None,
                "yaw_deg": None, "located": None, "home": _app(home)}
    r = tagmod.check_home(tagmod.detect_tags(frame), ref, home, _cols())
    r["home"] = _app(home)
    return r


def _frame_size(frame):
    return [int(frame.shape[1]), int(frame.shape[0])]


def _same_frame(ref, frame):
    """기준을 잡을 때와 화면 크기(회전)가 같은지. 예전 기준(frame 없음)은 1280x720 으로 본다."""
    return list(ref.get("frame", [1280, 720])) == _frame_size(frame)


def _frame_msg(ref, frame):
    a, b = ref.get("frame", [1280, 720]), _frame_size(frame)
    return f"카메라 화면이 {a[0]}x{a[1]} 에서 {b[0]}x{b[1]} 로 바뀌었습니다 (회전 설정 변경). 기준 등록을 다시 하세요."


def _publish(result, misaligned):
    """앱에 보일 결과. located 의 칸은 앱 좌표로."""
    r = dict(result)
    if r.get("located"):
        r["located"] = dict(r["located"], cell=_app(r["located"]["cell"]))
    r["checked_at"] = time.time()
    state.home_check = r
    state.home_misaligned = misaligned
    return r


def _job_view(job):
    if not job:
        return None
    return {k: v for k, v in job.items() if k not in ("before", "queue")}


def _drop_raw():
    state.current_path = [c for c in state.current_path if not str(c).startswith("raw:")]


def _send_raw(line):
    state.current_path = [f"raw:{line}"]


# ---------- 자동 보정 ----------
def _plan_correction(r):
    """가장 큰 오차 하나를 고른다. (방향, 그룹, 양) 또는 None(더 고칠 것 없음)."""
    dx, dy = r["error_cm"]
    yaw = r.get("yaw_deg")
    if yaw is not None and abs(yaw) > tagmod.YAW_TOL_DEG:
        return ("ccw" if yaw > 0 else "cw"), "rot", abs(yaw)          # 틀어짐부터 (좌우/앞뒤 방향이 맞아야 하므로)
    if max(abs(dx), abs(dy)) <= TARGET_CM:
        return None
    if abs(dx) >= abs(dy):
        return ("left" if dx > 0 else "right"), "lr", abs(dx)          # dx > 0: 동쪽으로 치우침 -> 왼쪽으로
    return ("forward" if dy > 0 else "backward"), "fb", abs(dy)        # dy > 0: 남쪽(뒤)으로 치우침 -> 앞으로


def _too_big(r):
    dx, dy = r["error_cm"]
    yaw = r.get("yaw_deg") or 0.0
    return max(abs(dx), abs(dy)) > AUTO_MAX_CM or abs(yaw) > AUTO_MAX_DEG


def _finish(job, r, ok, reason=None):
    job["status"] = "done" if ok else "failed"
    if reason:
        job["fail_reason"] = reason
    job["finished_at"] = time.time()
    state.tag_last_job = _job_view(job)
    state.tag_job = None
    _drop_raw()
    if ok:
        _publish(r, False)
    else:
        rr = dict(r or {"error_cm": None, "yaw_deg": None, "located": None})
        rr["ok"], rr["reason"] = False, reason or rr.get("reason", "misaligned")
        _publish(rr, True)
    print(f"[apriltag] job {job['kind']} {job['status']} {reason or ''} history={len(job.get('history', []))}", flush=True)


def _next_correction(job, r):
    """r(방금 잰 결과)를 보고 다음 nudge 를 내거나 끝낸다. state.lock 안에서 부른다."""
    if r["reason"] in ("tag_not_found", "camera_error", "recalibrate"):
        return _finish(job, r, False, r["reason"])
    if r["ok"]:                                    # 허용 범위(5cm, 3도) 안이면 끝
        return _finish(job, r, True)
    if _too_big(r):
        return _finish(job, r, False, "too_far")
    if job["step"] >= MAX_STEPS:
        return _finish(job, r, False, "too_many_steps")
    plan = _plan_correction(r)
    if plan is None:                                # 2.5cm 이하인데 ok 가 아니면 yaw 없이 판정한 경우뿐
        return _finish(job, r, True)
    d, grp, want = plan
    amt = plan_amount(grp, want)
    # 같은 방향으로 보냈는데 두 번 다 거의 안 움직였으면 포기
    stuck = [h for h in job["history"] if h["dir"] == d and (h["moved"] or 0) < 0.5]
    if len(stuck) >= 2:
        return _finish(job, r, False, "not_moving")
    job["step"] += 1
    job["pending"] = {"kind": "nudge", "dir": d, "grp": grp, "cmd": amt, "want": round(want, 1)}
    job["before"] = r
    _send_raw(_cmd_line(d, amt))
    _publish(dict(r, reason="correcting"), True)


def _moved(d, before, after):
    """명령한 방향으로 실제 움직인 양 (cm 또는 도). 잴 수 없으면 None."""
    b, a = before.get("located"), after.get("located")
    if not b or not a:
        return None
    if d == "forward":
        return b["y_cm"] - a["y_cm"]
    if d == "backward":
        return a["y_cm"] - b["y_cm"]
    if d == "right":
        return a["x_cm"] - b["x_cm"]
    if d == "left":
        return b["x_cm"] - a["x_cm"]
    if b["yaw_deg"] is None or a["yaw_deg"] is None:
        return None
    return (a["yaw_deg"] - b["yaw_deg"]) if d == "cw" else (b["yaw_deg"] - a["yaw_deg"])


def start_correction(r):
    """state.lock 안에서 부른다."""
    job = {"kind": "correct", "status": "running", "step": 0, "history": [],
           "start_error_cm": r.get("error_cm"), "start_yaw_deg": r.get("yaw_deg"), "started_at": time.time()}
    state.tag_job = job
    _next_correction(job, r)


def run_home_check(settle=True, auto=True):
    """사진을 찍어 홈 위치를 확인하고, 어긋났으면 자동 보정을 시작한다. 기준이 없으면 None."""
    r = _measure(settle)
    if r is None:
        return None
    with state.lock:
        if r["ok"]:
            _publish(r, False)
        elif auto and AUTO_CORRECT and r["reason"] == "misaligned" and not _too_big(r):
            start_correction(r)
        else:
            if r["reason"] == "misaligned" and _too_big(r):
                r = dict(r, reason="too_far")
            _publish(r, True)
        out = dict(state.home_check)
    print(f"[apriltag] home check: {r['reason']} error_cm={r.get('error_cm')} yaw={r.get('yaw_deg')}", flush=True)
    return out


def after_return_home():
    """/command/done 이 홈 도착을 알린 직후 부른다 (state.lock 밖에서)."""
    return run_home_check(settle=True)


def clear_home_check():
    """'시작점에 놓기' 때 부른다."""
    state.home_check = None
    state.home_misaligned = False
    state.tag_job = None


# ---------- 이동 거리 측정 ----------
CELL_PROBE_PPC = {"fb": "pulses_per_cm_fwd", "lr": "pulses_per_cm_strafe"}


def _measure_summary(job):
    cells = {}
    for h in job["history"]:
        if h["kind"] == "cell" and h["moved"] is not None:
            cells.setdefault(GROUP[h["dir"]], []).append(h["moved"])
    out = {}
    for grp, vals in cells.items():
        avg = sum(vals) / len(vals)
        cur = job["params"][CELL_PROBE_PPC[grp]]
        # 펌웨어는 34cm x PULSES_PER_CM 펄스를 세고 멈춘다. 실제로 avg cm 갔다면 1cm 당 펄스는 cur x 34 / avg.
        # (STOP_EARLY 이후 더 미끄러지는 양도 섞여 있으므로 근사치. 바꾼 뒤 다시 재서 확인한다)
        out[grp] = {"moved_cm": [round(v, 1) for v in vals], "avg_cm": round(avg, 1),
                    "current_pulses_per_cm": cur,
                    "recommended_pulses_per_cm": round(cur * tagmod.CELL_CM / avg, 1) if avg > 1 else None}
    models = {}
    for grp in ("fb", "lr", "rot"):
        m = nudge_model(grp)
        if m:
            models[grp] = {"scale": round(m["scale"], 2), "unit": UNIT[grp], "samples": m["n"]}
    return {"cell_move": out, "nudge_model": models}


def _next_measure(job, r):
    if r["reason"] in ("tag_not_found", "camera_error", "recalibrate"):
        return _finish(job, r, False, r["reason"])
    if not job["queue"]:
        job["summary"] = _measure_summary(job)
        state.tag_last_measure = job["summary"]
        # 끝나면 홈 중앙으로 다시 맞춘다
        job["kind"], job["step"], job["queue"] = "correct", 0, []
        job["measure_history"], job["history"] = job["history"], []
        return _next_correction(job, r)
    kind, line = job["queue"].pop(0)
    job["step"] += 1
    d, amt = _parse_line(line)
    job["pending"] = {"kind": kind, "dir": d, "grp": GROUP[d],
                      "cmd": amt if kind == "nudge" else None, "line": line}
    job["before"] = r
    _send_raw(line)
    _publish(dict(r, reason="measuring"), True)


class MeasureParams(BaseModel):
    pulses_per_cm_fwd: float = 32.5      # 지금 펌웨어의 PULSES_PER_CM_FWD
    pulses_per_cm_strafe: float = 32.3   # 지금 펌웨어의 PULSES_PER_CM_STRAFE
    reset: bool = True                   # 이전에 학습한 짧은 이동 샘플을 지우고 새로 잰다
    nudge_cm: list[int] = [3, 8]         # 짧은 이동 (1~15cm)
    rotate_deg: list[int] = [5, 15]      # 제자리 회전 (도)


def _free(grid, x, y):
    return 0 <= y < len(grid) and 0 <= x < len(grid[0]) and grid[y][x] != 1


@router.post("/apriltag/measure-moves", dependencies=[Depends(require_admin)])
def measure_moves(p: MeasureParams = MeasureParams()):
    from server.routers import obstacle
    if load_ref() is None:
        raise HTTPException(status_code=400, detail="기준이 없습니다. 로봇을 홈에 놓고 /apriltag/calibrate 를 먼저 하세요.")
    with state.lock:
        _require_idle_at_home(obstacle)
        grid = obstacle._grid()
        hx, hy = _home()
    probes = []
    if _free(grid, hx, hy - 1):
        probes += [("cell", "forward 1"), ("cell", "backward 1")]
    elif _free(grid, hx, hy + 1):
        probes += [("cell", "backward 1"), ("cell", "forward 1")]
    if _free(grid, hx + 1, hy):
        probes += [("cell", "right 1"), ("cell", "left 1")]
    elif _free(grid, hx - 1, hy):
        probes += [("cell", "left 1"), ("cell", "right 1")]
    for a, b in (("forward", "backward"), ("right", "left")):
        for cm in p.nudge_cm:
            cm = int(min(max(cm, CMD_MIN["fb"]), CMD_MAX["fb"]))
            probes += [("nudge", _cmd_line(a, cm)), ("nudge", _cmd_line(b, cm))]
    for deg in p.rotate_deg:
        deg = int(min(max(deg, CMD_MIN["rot"]), CMD_MAX["rot"]))
        probes += [("nudge", _cmd_line("cw", deg)), ("nudge", _cmd_line("ccw", deg))]
    if p.reset:
        clear_samples()
    r = _measure(settle=False)
    if r is None or r["reason"] in ("tag_not_found", "camera_error", "recalibrate"):
        raise HTTPException(status_code=400, detail=f"태그로 위치를 잴 수 없습니다: {r and (r.get('detail') or r['reason'])}")
    with state.lock:
        job = {"kind": "measure", "status": "running", "step": 0, "history": [], "queue": list(probes),
               "params": p.model_dump(), "started_at": time.time()}
        state.tag_job = job
        _next_measure(job, r)
    return {"status": "started", "probes": [l for _, l in probes]}


def _require_idle_at_home(obstacle):
    pos, home = obstacle._robot_pos(), _home()
    busy = (state.current_path or getattr(state, "mission", None) or getattr(state, "pending_move", None)
            or getattr(state, "tag_job", None))
    if pos is None or home is None or tuple(pos) != tuple(home) or busy:
        raise HTTPException(status_code=409, detail="로봇이 홈에 멈춰 있고 다른 작업이 없을 때만 할 수 있습니다.")


# ---------- 브리지가 raw 명령을 끝냈을 때 ----------
class JobDone(BaseModel):
    ok: bool
    reply: str = ""


@router.post("/apriltag/job-done")
def job_done(j: JobDone):
    job = getattr(state, "tag_job", None)
    if job is None:
        return {"status": "no_job"}
    if not j.ok:
        with state.lock:
            _finish(job, job.get("before"), False, f"esp32:{j.reply}")
        return {"status": "failed"}
    r = _measure(settle=True)
    with state.lock:
        if state.tag_job is not job:                  # 그 사이 '시작점에 놓기' 등으로 취소됨
            return {"status": "cancelled"}
        pend = job.pop("pending", {})
        moved = _moved(pend.get("dir"), job.get("before") or {}, r) if r else None
        h = {"kind": pend.get("kind", "nudge"), "dir": pend.get("dir"), "cmd": pend.get("cmd"),
             "want": pend.get("want"), "moved": None if moved is None else round(moved, 1),
             "error_after_cm": r and r.get("error_cm"), "yaw_after": r and r.get("yaw_deg")}
        job["history"].append(h)
        if h["kind"] == "nudge" and moved is not None and pend.get("cmd"):
            add_sample(pend["grp"], pend["cmd"], moved)
        print(f"[apriltag] {h['kind']} {h['dir']} {h['cmd'] or ''} -> moved {h['moved']} "
              f"(want {h['want']}) error={h['error_after_cm']} yaw={h['yaw_after']}", flush=True)
        if r is None:
            _finish(job, None, False, "no_reference")
        elif job["kind"] == "measure":
            _next_measure(job, r)
        else:
            _next_correction(job, r)
        return {"status": (state.tag_job or {}).get("status", "finished"), "history": h}


# ---------- API ----------
@router.post("/apriltag/calibrate", dependencies=[Depends(require_admin)])
def calibrate():
    home, cols = _home(), _cols()
    if home is None or not cols:
        raise HTTPException(status_code=400, detail="격자 지도 또는 시작점이 없습니다.")
    frame = capture()
    tags = tagmod.detect_tags(frame)
    ref, err = tagmod.calibrate(tags, home, cols, frame_size=_frame_size(frame))
    if ref is None:
        raise HTTPException(status_code=400, detail=err)
    save_ref(ref)
    with state.lock:
        clear_home_check()
    return {"status": "calibrated", "ref": ref, "tags": [{"id": t["id"], "size_px": round(t["size_px"], 1)} for t in tags]}


@router.get("/apriltag/detect")
def detect():
    frame = capture()
    tags = tagmod.detect_tags(frame)
    ref, cols = load_ref(), _cols()
    if ref is not None and not _same_frame(ref, frame):
        return {"calibrated": True, "recalibrate": _frame_msg(ref, frame),
                "tags": [{k: t[k] for k in ("id", "cx", "cy", "size_px")} for t in tags], "located": None}
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
    from server.routers import obstacle
    if load_ref() is None:
        raise HTTPException(status_code=400, detail="기준이 없습니다. 로봇을 홈에 놓고 /apriltag/calibrate 를 먼저 하세요.")
    with state.lock:
        _require_idle_at_home(obstacle)
    return run_home_check(settle=False)


@router.get("/apriltag/status")
def status():
    return {
        "calibrated": load_ref() is not None,
        "job": _job_view(getattr(state, "tag_job", None)),
        "last_job": getattr(state, "tag_last_job", None),
        "last_measure": getattr(state, "tag_last_measure", None),
        "home_check": getattr(state, "home_check", None),
        "nudge_model": {g: nudge_model(g) for g in ("fb", "lr", "rot")},
    }
