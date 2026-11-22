import functools
import threading

current_command = "stop"
current_path = []

# 배송 진행 상황 추적용
current_item_qr = None   # 지금 배송 중인 물품의 QR 코드 (/route에서 설정)
current_steps = 0        # 마지막으로 /next-command에서 보낸 칸 수
goal = None
pending_move = None
skip_detect = False

# 복귀 관련
mission = None          # "deliver"(배송 중) / "return"(홈 복귀 중) / None
return_at = None        # 자동 복귀 예약 시각 (time.time() 기준)


placed_at = 0.0

# AprilTag 홈 위치 확인 (server/routers/apriltag.py)
home_check = None       # 마지막 확인 결과
home_misaligned = False # True 면 대기열 출발/새 배송을 막는다 (시작점에 놓기 또는 다시 확인으로 해제)
dest_check = None       # 마지막 배송지 도착 위치 확인 결과 (apriltag.after_arrive)
tag_job = None          # 진행 중인 자동 보정/이동 측정 (apriltag.py)
tag_last_job = None
tag_last_measure = None   # 마지막으로 '시작점에 놓기'를 한 시각 (브리지 halt 해제 신호)
# 옆이동(left/right) 전후 위치 확인 (apriltag.route_check_hold)
route_check = None        # 마지막 결과
route_checking = False    # 사진 찍는 중: /next-command 가 잠깐 대기를 돌려준다
route_checked_key = None  # 이미 확인한 (위치, 남은 경로) - 보정 뒤 같은 자리에서 다시 찍지 않게
yaw2_obs = None           # 두 거리 yaw 계산용 마지막 측정 (apriltag._yaw2)

# 배송 대기열: 배송·복귀 중에 인식된 물품은 여기 쌓였다가,
# 로봇이 시작점에 돌아오면 먼저 인식된 순서대로 시작점에서 출발한다.
delivery_queue = []     # QR 코드 목록
next_start_at = None    # 대기열 다음 물품 출발 예약 시각 (시작점에서 싣는 시간)

# 사람 다리 대기 (server/person_detect.py, obstacle.py)
person_wait_until = None   # 이 시각까지 /next-command 가 대기를 돌려준다
person_wait_count = 0      # 같은 자리에서 연속으로 사람 때문에 기다린 횟수

# /route 와 /next-command 가 배송 상태를 동시에 바꾸지 않게 한다
lock = threading.RLock()



def locked(fn):
    """배송 상태(경로, 막힌 칸, 위치)를 읽거나 바꾸는 엔드포인트에 붙인다. RLock 이라 안에서 또 잡아도 된다."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with lock:
            return fn(*args, **kwargs)
    return wrapper
