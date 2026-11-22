"""AprilTag(tag36h11)로 로봇 위치를 확인하는 모듈. FastAPI/카메라 없이 프레임만 받아서 계산한다.

배치 규칙
  - 태그는 격자 북쪽 가장자리 바깥에 세워서 붙인다. 로봇은 항상 북쪽을 보므로 전면 카메라에 보인다.
  - 태그 ID 0 = 0열 가운데 위, 그다음 ID 부터 TAG_PITCH_CM 간격으로 동쪽으로.
    TAG_PITCH_CM = 34 이면 ID = 열 번호, 17 이면 짝수 ID = 열 가운데(열 번호 x2), 홀수 ID = 열 경계.
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
TAG_SIZE_CM = 5.0        # 태그 검은 부분 한 변 (인쇄 후 자로 재서 맞출 것)
CAMERA_OFFSET_CM = 12.0  # 로봇 중심 -> 카메라 렌즈 (앞쪽으로). 실측해서 맞출 것
TAG_GAP_CM = 10.0         # 북쪽 가장자리 -> 태그 판
HOME_TOL_CM = 5.0         # 홈 중앙에서 이만큼까지는 정상
YAW_TOL_DEG = 2.0         # 이만큼까지 틀어진 건 정상 (틀어짐을 잴 수 있을 때만)
SINGLE_PNP_MIN_PX = 160   # 태그 1개만 보일 때 이 크기(px) 이상이면 그 태그 하나로 틀어짐까지 푼다
EDGE_MARGIN_PX = 8        # 화면 가장자리에서 이만큼 안쪽에 있어야 쓴다
# 태그가 한 판(같은 평면)에 좁게 모여 있고 멀리 있으면(홈이 아랫줄) PnP 의 틀어짐(yaw)과 좌우 위치가 서로 구분이 안 된다.
#   예: 153cm 밖 5cm 태그(약 62px)는 태그 간격이 2cm 어긋나거나 렌즈 왜곡이 있으면 yaw 24도 + 좌우 -40cm 같은 답이 나온다.
# 그래서 PnP 는 가장 큰 태그가 SINGLE_PNP_MIN_PX 이상으로 보일 때(가까워서 태그 안의 원근이 보일 때)만 쓴다.
# 각도 크기로는 거르지 않는다 (실제로 10도 넘게 돌아갔을 수도 있으므로). 작으면 태그 1개 방식 + yaw 없음.
# [2026-11-22] 멀리 있을 때 틀어짐(yaw) 추정
#   멀면 태그 하나로 '좌우로 밀림'과 '틀어짐'을 구분할 수 없다 (둘 다 태그가 화면에서 옆으로 가 보인다).
#   그런데 150cm 에서 3도 틀어지면 태그가 8cm 옆으로 밀린 것처럼 보이고, 반대로 3cm 밀려도 1도밖에 안 된다.
#   그래서 멀 때(FAR_YAW_CM 이상)는 태그가 옆으로 보이는 것을 '틀어짐'으로 읽고, 좌우 위치는 기대한 칸 중앙으로 둔다.
#   (예전엔 이걸 좌우 밀림으로 읽어 nudge 로 옆으로 움직여서, 틀어짐은 그대로 두고 위치만 더 틀어졌다)
FAR_YAW = True
FAR_YAW_CM = 80.0         # 렌즈 -> 태그 거리가 이 이상이면 멀다고 본다

TAG_PITCH_CM = 17.0       # 태그 간격. 34 = 열마다 1개 (ID = 열 번호)
                          # 17 = 반 칸마다 1개 (짝수 ID = 열 가운데, 홀수 ID = 열 경계). 카메라를 세로로 쓰면 17 권장

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
    H, W = gray.shape[:2]
    for c, i in zip(corners, ids.ravel()):
        p = c.reshape(4, 2)
        sides = [np.linalg.norm(p[k] - p[(k + 1) % 4]) for k in range(4)]
        # 화면 가장자리에 걸친 태그는 꼭짓점이 부정확해서 쓰지 않는다 (흰 여백까지 화면 안에 있어야 함)
        margin = max(EDGE_MARGIN_PX, 0.25 * float(np.mean(sides)))
        if (p[:, 0].min() < margin or p[:, 1].min() < margin
                or p[:, 0].max() > W - 1 - margin or p[:, 1].max() > H - 1 - margin):
            continue
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
    """태그 중심의 x(cm). ID 0 = 0열 가운데, 그다음부터 TAG_PITCH_CM 간격."""
    return CELL_CM / 2 + tag_id * TAG_PITCH_CM


def tag_count(cols):
    """격자 폭에 들어가는 태그 수 (ID 0 ~ tag_count-1)."""
    return int(round((cols - 1) * CELL_CM / TAG_PITCH_CM)) + 1


def home_tag_id(home):
    """홈 칸 바로 앞(북쪽) 태그 ID."""
    return int(round(home[0] * CELL_CM / TAG_PITCH_CM))


def _camera_to_tag_cm(robot_y_cm):
    """로봇 중심이 robot_y_cm 일 때 렌즈에서 태그 판까지 거리."""
    return robot_y_cm + TAG_GAP_CM - CAMERA_OFFSET_CM


def calibrate(tags, home, cols, frame_size=(1280, 720)):
    """로봇이 홈 칸 중앙에 있을 때의 태그로 기준값을 만든다. 실패하면 (None, 이유).

    frame_size: (가로, 세로) px. 카메라를 90도 돌려 쓰면 (720, 1280).
    """
    hid = home_tag_id(home)
    known = [t for t in tags if t["id"] == hid]              # 홈 칸 바로 앞 태그로만 기준을 잡는다
    if not known:
        seen = sorted({t["id"] for t in tags})
        return None, (f"홈 칸 앞 태그(ID {hid})가 보이지 않습니다. 보이는 태그: {seen or '없음'}. "
                      f"홈 칸 바로 북쪽에 ID {hid} 태그를 붙였는지 확인하세요 (TAG_PITCH_CM = {TAG_PITCH_CM:g}).")
    t = known[0]
    hx, hy = cell_center_cm(home)
    d = _camera_to_tag_cm(hy)
    if d <= 0:
        return None, "카메라와 태그 판 사이 거리가 0 이하입니다. TAG_GAP_CM / CAMERA_OFFSET_CM 을 확인하세요."
    fx = t["size_px"] * d / TAG_SIZE_CM
    lateral = _tag_x_cm(t["id"]) - hx               # 태그가 카메라보다 오른쪽(+)
    cx0 = t["cx"] - fx * lateral / d
    ref = {"fx": fx, "cx0": cx0, "cy0": frame_size[1] / 2.0, "frame": list(frame_size), "tag_id": t["id"],
           "home": list(home), "size_px": round(t["size_px"], 2)}

    # (예전에는 태그가 2개 이상 보이면 PnP 결과로 fx, cx0 를 다듬었다. 그런데 PnP 가 yaw/좌우를 잘못 풀면
    #  cx0 가 화면 밖(예: 폭 720 인데 2029)으로 끌려가서 이후 위치가 거리만큼(±150cm) 틀어졌다. 그래서 다듬지 않는다)
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


def locate(tags, ref, cols, expect_x_cm=None):
    """보이는 태그로 로봇 중심 위치(cm)와 칸을 구한다. 태그가 없으면 None.

    태그 2개 이상, 또는 1개라도 크게(SINGLE_PNP_MIN_PX 이상) 보이면 PnP 로 틀어짐(yaw)까지 풀어서 계산한다.
    작은 태그 1개뿐이면 틀어짐 0 으로 가정한다 (yaw_deg = None). 이때는 2~3도만 틀어져도 좌우 오차가 몇 cm 생긴다.

    반환: {"tag_ids", "method", "x_cm", "y_cm", "yaw_deg", "cell": [x, y], "offset_cm": [dx, dy]}
          offset_cm = 그 칸 중앙에서 벗어난 양 (dx: 동쪽 +, dy: 남쪽 +)
    """
    known = [t for t in tags if 0 <= t["id"] < tag_count(cols)]
    if not known or ref is None:
        return None
    yaw = None
    big = max(known, key=lambda k: k["size_px"])
    res = None
    if big["size_px"] >= SINGLE_PNP_MIN_PX:          # 가까울 때만 PnP (멀면 yaw/좌우가 구분 안 됨)
        res = _locate_pnp(known, ref) if len({k["id"] for k in known}) >= 2 else _locate_pnp([big], ref)
    if res is not None:
        x, y, yaw = res
        method = "pnp" if len({k["id"] for k in known}) >= 2 else "pnp_single"
        used = sorted({k["id"] for k in known}) if method == "pnp" else [big["id"]]
    else:
        t = min(known, key=lambda k: abs(k["cx"] - ref["cx0"]))   # 화면 가운데에 가장 가까운(정면) 태그
        x, y = _locate_single(t, ref)
        method, used = "single", [t["id"]]
        d = ref["fx"] * TAG_SIZE_CM / t["size_px"]                # 렌즈 -> 태그 거리
        if FAR_YAW and expect_x_cm is not None and d >= FAR_YAW_CM:
            # 기대 위치(칸 중앙)에서 보면 태그가 화면 어디에 보여야 하는지와 실제 위치의 각도 차 = 틀어짐
            expect_bearing = math.atan2(_tag_x_cm(t["id"]) - expect_x_cm, d)
            seen_bearing = math.atan2(t["cx"] - ref["cx0"], ref["fx"])
            yaw = math.degrees(expect_bearing - seen_bearing)       # 동쪽(시계)으로 틀어지면 +
            x = expect_x_cm
            method = "single_far_yaw"
    cell = [int(math.floor(x / CELL_CM)), int(math.floor(y / CELL_CM))]
    cxm, cym = cell_center_cm(cell)
    return {"tag_ids": used, "method": method, "x_cm": round(x, 1), "y_cm": round(y, 1),
            "yaw_deg": None if yaw is None else round(yaw, 1), "cell": cell,
            "offset_cm": [round(x - cxm, 1), round(y - cym, 1)]}


def check_home(tags, ref, home, cols, tol_cm=HOME_TOL_CM, yaw_tol_deg=YAW_TOL_DEG, far_yaw=True):
    """홈 칸 중앙에 제대로 서 있는지. 틀어짐(yaw)을 잴 수 있으면 yaw_tol_deg 도 본다.

    far_yaw=False: 멀어도 태그가 옆으로 보이는 것을 좌우 위치로 읽는다 (이동 거리 측정용. 켜 두면 좌우 이동이 0 으로 잡힌다)
    반환: {"ok": bool, "reason", "error_cm": [dx, dy] 또는 None, "yaw_deg", "located": locate 결과}
    """
    hx0, _ = cell_center_cm(home)
    loc = locate(tags, ref, cols, expect_x_cm=hx0 if far_yaw else None)
    if loc is None:
        return {"ok": False, "reason": "tag_not_found", "error_cm": None, "yaw_deg": None, "located": None}
    hx, hy = cell_center_cm(home)
    dx, dy = round(loc["x_cm"] - hx, 1), round(loc["y_cm"] - hy, 1)
    FAR_YAW_TOL_DEG = 5.0     # 멀리서 읽은 yaw 는 밀림이 섞여 있어 크게 둔다 (83cm 에서 7cm 밀림 = 5도)

    yaw = loc["yaw_deg"]
    ytol = FAR_YAW_TOL_DEG if loc["method"] == "single_far_yaw" else yaw_tol_deg
    ok = abs(dx) <= tol_cm and abs(dy) <= tol_cm and (yaw is None or abs(yaw) <= ytol)
    return {"ok": ok, "reason": "ok" if ok else "misaligned", "error_cm": [dx, dy], "yaw_deg": yaw, "located": loc}
