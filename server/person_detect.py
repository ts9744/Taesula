"""사람 다리 인식 -> 잠시 대기 후 같은 이동을 다시 시도.

초음파가 장애물을 보고했을 때 앞쪽 카메라로 한 장 찍어 YOLO 를 돌린다.
'Leg'(사람 다리)가 보이면 그 칸을 막지 않고 PERSON_WAIT_SEC 만큼 기다렸다가 같은 이동을 다시 보낸다.
(로봇이 출발 전에 다시 센서로 확인하므로, 사람이 비켰으면 그대로 간다)
PERSON_MAX_WAITS 번 연속으로 사람이 보이면 일반 장애물로 처리한다 (막힌 칸 + 재탐색).

- 카메라는 로봇 앞(격자 북쪽)만 보므로 forward 이동에서만 판단한다.
- 카메라/YOLO 가 실패하거나 모델에 'Leg' 클래스가 없으면 사람이 아닌 것으로 본다 (지금까지와 같은 동작).
"""
PERSON_LABEL = "Leg"            # detector.CLASS_NAMES 에 들어갈 이름
PERSON_MIN_SCORE = 0.5          # 이 점수 이상인 박스만 사람으로 본다
PERSON_MIN_HEIGHT_RATIO = 0.2   # 박스 높이가 화면 높이의 이 비율 이상 (멀리 있는 사람은 무시)
PERSON_WAIT_SEC = 3.0           # 한 번 기다리는 시간
PERSON_MAX_WAITS = 5            # 연속 대기 최대 횟수 (넘으면 일반 장애물)
CAMERA_DIRECTIONS = ("forward",)


def _is_person(det, frame_h):
    if det.get("label") != PERSON_LABEL or det.get("score", 0) < PERSON_MIN_SCORE:
        return False
    x1, y1, x2, y2 = det["box"]
    return (y2 - y1) >= frame_h * PERSON_MIN_HEIGHT_RATIO


def person_ahead():
    """앞쪽 카메라에 사람 다리가 보이면 True. 실패하면 False (일반 장애물로 처리되게)."""
    try:
        from server.camera.camera import get_frame
        from server.camera.detector import detect
        frame = get_frame()
        dets = detect(frame)
    except Exception as e:                      # 카메라/Hailo 없음, 추론 실패 등
        print("person detect skipped:", e)
        return False
    return any(_is_person(d, frame.shape[0]) for d in dets)
