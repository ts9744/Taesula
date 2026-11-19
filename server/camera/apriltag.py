"""AprilTag(tag36h11)로 로봇 위치를 확인하는 모듈. FastAPI/카메라 없이 프레임만 받아서 계산한다.

배치 규칙
  - 태그는 격자 북쪽 가장자리 바깥에 세워서 붙인다. 로봇은 항상 북쪽을 보므로 전면 카메라에 보인다.
  - 태그 ID = 그 태그가 붙은 열 번호 x (0부터). 태그 중심은 그 열의 가운데 위.
  - 태그 판은 북쪽 가장자리에서 TAG_GAP_CM 만큼 떨어뜨린다.
    (초음파 STOP_DISTANCE_CM = 10 이라, 붙여 두면 맨 윗줄로 갈 때 태그 판을 장애물로 본다)

캘리브레이션
  - 로봇을 홈 칸 중앙에 정확히 놓고 calibrate() 를 한 번 부른다.
  - 그때 태그의 화면 크기와 위치로 초점거리(fx)와 화면 중심(cx0)을 구해 둔다. 체커보드 캘리브레이션은 필요 없다.
"""
import math

import cv2
import numpy as np

CELL_CM = 34.0
TAG_SIZE_CM = 10.0        # 태그 검은 부분 한 변 (인쇄 후 자로 재서 맞출 것)
CAMERA_OFFSET_CM = 10.0   # 로봇 중심 -> 카메라 렌즈 (앞쪽으로). 실측해서 맞출 것
TAG_GAP_CM = 10.0         # 북쪽 가장자리 -> 태그 판
HOME_TOL_CM = 5.0         # 홈 중앙에서 이만큼까지는 정상
YAW_TOL_DEG = 3.0         # 이만큼까지 틀어진 건 정상 (틀어짐을 잴 수 있을 때만)
SINGLE_PNP_MIN_PX = 120   # 태그 1개만 보일 때 이 크기(px) 이상이면 그 태그 하나로 틀어짐까지 푼다

_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
_params = cv2.aruco.DetectorParameters()
_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_APRILTAG
_detector = cv2.aruco.ArucoDetector(_dict, _params)


def detect_tags(frame_bgr):
    """프레임(Picamera2 RGB888 = 메모리상 BGR)에서 태그를 찾는다.

    반환: [{"id", "cx", "cy", "size_px", "corners"}] (크기가 큰 = 가까운 순)
    """
    gray = frame_bgr if frame_bgr.ndim == 2 else cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = _detector.detectMarkers(gray)
    tags = []
    if ids is None:
        return tags
    for c, i in zip(corners, ids.ravel()):
        p = c.reshape(4, 2)
        sides = [np.linalg.norm(p[k] - p[(k + 1) % 4]) for k in range(4)]
        tags.append({
            "id": int(i),
            "cx": float(p[:, 0].mean()),
            "cy": float(p[:, 1].mean()),
            "size_px": float(np.mean(sides)),
            "corners": p.round(1).tolist(),
        })
    tags.sort(key=lambda t: -t["size_px"])
    return tags


def cell_center_cm(cell):
    """칸 (x, y) 중앙의 cm 좌표. 원점 = 격자 북서쪽 모서리, x 는 동쪽 +, y 는 남쪽 +."""
    return (cell[0] + 0.5) * CELL_CM, (cell[1] + 0.5) * CELL_CM


def _tag_x_cm(tag_id):
    return (tag_id + 0.5) * CELL_CM


def _camera_to_tag_cm(robot_y_cm):
    """로봇 중심이 robot_y_cm 일 때 렌즈에서 태그 판까지 거리."""
    return robot_y_cm + TAG_GAP_CM - CAMERA_OFFSET_CM


def calibrate(tags, home, cols):
    """로봇이 홈 칸 중앙에 있을 때의 태그로 기준값을 만든다. 실패하면 (None, 이유)."""
    known = [t for t in tags if t["id"] == home[0]]          # 홈 열의 태그로만 기준을 잡는다
    if not known:
        seen = sorted({t["id"] for t in tags})
        return None, (f"홈 열 태그(ID {home[0]})가 보이지 않습니다. 보이는 태그: {seen or '없음'}. "
                      "홈 칸 바로 북쪽에 ID = 열 번호 태그를 붙였는지 확인하세요.")
    t = known[0]
    hx, hy = cell_center_cm(home)
    d = _camera_to_tag_cm(hy)
    if d <= 0:
        return None, "카메라와 태그 판 사이 거리가 0 이하입니다. TAG_GAP_CM / CAMERA_OFFSET_CM 을 확인하세요."
    fx = t["size_px"] * d / TAG_SIZE_CM
    lateral = _tag_x_cm(t["id"]) - hx               # 태그가 카메라보다 오른쪽(+)
    cx0 = t["cx"] - fx * lateral / d
    ref = {"fx": fx, "cx0": cx0, "cy0": 360.0, "tag_id": t["id"],
           "home": list(home), "size_px": round(t["size_px"], 2)}

    # 태그가 2개 이상 보이면 PnP 결과가 홈 칸 중앙과 맞도록 fx, cx0 를 다듬는다
    multi = [k for k in tags if 0 <= k["id"] < cols]
    if len({k["id"] for k in multi}) >= 2:
        for _ in range(5):
            res = _locate_pnp(multi, ref)
            if res is None:
                break
            x, y, _yaw = res
            ref["fx"] *= d / _camera_to_tag_cm(y)          # 거리는 fx 에 비례
            ref["cx0"] -= ref["fx"] * (x - hx) / d         # 좌우 어긋남만큼 화면 중심 이동
    ref["fx"], ref["cx0"] = round(ref["fx"], 2), round(ref["cx0"], 2)
    return ref, None


def _tag_corners_world(tag_id):
    """PnP 용 태그 네 꼭짓점 (월드: X 동쪽, Y 아래, Z 북쪽. 원점 = 북서 모서리, 높이는 태그 중심)."""
    tx, h, z = _tag_x_cm(tag_id), TAG_SIZE_CM / 2, TAG_GAP_CM
    return [[tx - h, -h, z], [tx + h, -h, z], [tx + h, h, z], [tx - h, h, z]]   # 좌상, 우상, 우하, 좌하


def _locate_pnp(known, ref):
    """태그 2개 이상: 모든 꼭짓점으로 자세를 풀어 위치와 틀어짐(yaw)을 같이 구한다."""
    obj = np.float32([p for t in known for p in _tag_corners_world(t["id"])])
    img = np.float32([p for t in known for p in t["corners"]])
    fx, cx0 = ref["fx"], ref["cx0"]
    K = np.float32([[fx, 0, cx0], [0, fx, ref.get("cy0", 360.0)], [0, 0, 1]])
    ok, rvec, tvec = cv2.solvePnP(obj, img, K, None, flags=cv2.SOLVEPNP_SQPNP)
    if not ok:
        return None
    R, _ = cv2.Rodrigues(rvec)
    cam = (-R.T @ tvec).ravel()                    # 카메라 위치 (월드)
    head = R.T @ np.array([0.0, 0.0, 1.0])         # 카메라가 보는 방향
    yaw = math.atan2(head[0], head[2])             # 북쪽 기준, 동쪽으로 틀어지면 +
    x = cam[0] - CAMERA_OFFSET_CM * math.sin(yaw)
    y = -cam[2] + CAMERA_OFFSET_CM * math.cos(yaw)
    return float(x), float(y), math.degrees(yaw)


def _locate_single(t, ref):
    """태그 1개: 틀어짐이 없다고 보고 크기(거리)와 화면 위치(좌우)로 구한다."""
    fx, cx0 = ref["fx"], ref["cx0"]
    d = fx * TAG_SIZE_CM / t["size_px"]
    lateral = (t["cx"] - cx0) * d / fx
    return _tag_x_cm(t["id"]) - lateral, d - TAG_GAP_CM + CAMERA_OFFSET_CM


def locate(tags, ref, cols):
    """보이는 태그로 로봇 중심 위치(cm)와 칸을 구한다. 태그가 없으면 None.

    태그 2개 이상, 또는 1개라도 크게(SINGLE_PNP_MIN_PX 이상) 보이면 PnP 로 틀어짐(yaw)까지 풀어서 계산한다.
    작은 태그 1개뿐이면 틀어짐 0 으로 가정한다 (yaw_deg = None). 이때는 2~3도만 틀어져도 좌우 오차가 몇 cm 생긴다.

    반환: {"tag_ids", "method", "x_cm", "y_cm", "yaw_deg", "cell": [x, y], "offset_cm": [dx, dy]}
          offset_cm = 그 칸 중앙에서 벗어난 양 (dx: 동쪽 +, dy: 남쪽 +)
    """
    known = [t for t in tags if 0 <= t["id"] < cols]
    if not known or ref is None:
        return None
    yaw = None
    if len({t["id"] for t in known}) >= 2:
        res = _locate_pnp(known, ref)
    else:
        big = max(known, key=lambda k: k["size_px"])
        res = _locate_pnp([big], ref) if big["size_px"] >= SINGLE_PNP_MIN_PX else None
    if res is not None:
        x, y, yaw = res
        method = "pnp" if len({t["id"] for t in known}) >= 2 else "pnp_single"
        used = sorted({t["id"] for t in known}) if method == "pnp" else [big["id"]]
    else:
        t = min(known, key=lambda k: abs(k["cx"] - ref["cx0"]))   # 화면 가운데에 가장 가까운(정면) 태그
        x, y = _locate_single(t, ref)
        method, used = "single", [t["id"]]
    cell = [int(math.floor(x / CELL_CM)), int(math.floor(y / CELL_CM))]
    cxm, cym = cell_center_cm(cell)
    return {"tag_ids": used, "method": method, "x_cm": round(x, 1), "y_cm": round(y, 1),
            "yaw_deg": None if yaw is None else round(yaw, 1), "cell": cell,
            "offset_cm": [round(x - cxm, 1), round(y - cym, 1)]}


def check_home(tags, ref, home, cols, tol_cm=HOME_TOL_CM, yaw_tol_deg=YAW_TOL_DEG):
    """홈 칸 중앙에 제대로 서 있는지. 틀어짐(yaw)을 잴 수 있으면 yaw_tol_deg 도 본다.

    반환: {"ok": bool, "reason", "error_cm": [dx, dy] 또는 None, "yaw_deg", "located": locate 결과}
    """
    loc = locate(tags, ref, cols)
    if loc is None:
        return {"ok": False, "reason": "tag_not_found", "error_cm": None, "yaw_deg": None, "located": None}
    hx, hy = cell_center_cm(home)
    dx, dy = round(loc["x_cm"] - hx, 1), round(loc["y_cm"] - hy, 1)
    yaw = loc["yaw_deg"]
    ok = abs(dx) <= tol_cm and abs(dy) <= tol_cm and (yaw is None or abs(yaw) <= yaw_tol_deg)
    return {"ok": ok, "reason": "ok" if ok else "misaligned", "error_cm": [dx, dy], "yaw_deg": yaw, "located": loc}
