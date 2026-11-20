import cv2
import os
import time
import asyncio
import concurrent.futures
import threading
from threading import Lock
from fastapi import HTTPException

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None


camera = None
camera_lock = Lock()
STREAM_LONG_SIDE = 480    # 스트림의 긴 변(px). 비율은 원본(회전 후)을 따른다 (QR 인식은 원본 그대로 사용)
STREAM_QUALITY = 60        # JPEG 품질 (기본 95)
STREAM_FPS = 15            # 초당 프레임 수
CAPTURE_TIMEOUT = 3        # 프레임 대기 최대 시간(초)
camera_closing = None   # 망가진 카메라를 정리 중인 스레드

# Python 3.11+ 에서는 둘이 같은 클래스지만, 버전 차이에 대비해 둘 다 잡는다
CAPTURE_TIMEOUT_ERRORS = (TimeoutError, concurrent.futures.TimeoutError)

# 카메라를 기울여 달아서 돌려 봐야 할 때: 반시계(왼쪽) 방향 각도. 0 / 90 / 180 / 270
#   90 = 왼쪽으로 90도 -> 프레임이 1280x720 가로에서 720x1280 세로가 된다
#   라즈베리파이 카메라는 하드웨어(libcamera Transform)로 90도를 못 돌려서 받은 뒤 OpenCV 로 돌린다
#   코드를 고치지 않고 바꾸려면 환경변수 TAESULA_CAMERA_ROTATE=270 처럼 준다
#   바꾼 뒤에는 /apriltag/calibrate 를 다시 해야 한다
CAMERA_ROTATE = int(os.environ.get("TAESULA_CAMERA_ROTATE", "90"))
_ROTATE_CODE = {
    0: None,
    90: cv2.ROTATE_90_COUNTERCLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_CLOCKWISE,
}
if CAMERA_ROTATE not in _ROTATE_CODE:
    raise ValueError(f"TAESULA_CAMERA_ROTATE 는 0/90/180/270 중 하나여야 합니다: {CAMERA_ROTATE}")


def rotate_frame(frame):
    code = _ROTATE_CODE[CAMERA_ROTATE]
    return frame if code is None else cv2.rotate(frame, code)


def get_camera():
    global camera

    if Picamera2 is None:
        raise HTTPException(status_code=500, detail="Picamera2가 설치되어 있지 않습니다.")

    if camera is None:
        cam = Picamera2()
        try:
            config = cam.create_preview_configuration(
                main={"size": (1280, 720), "format": "RGB888"}
            )
            cam.configure(config)
            cam.start()
            time.sleep(1)
        except Exception:
            try:
                cam.close()
            except Exception:
                pass
            raise
        camera = cam   # 초기화가 끝난 뒤에만 전역에 넣는다

    return camera

def _reset_camera():
    """타임아웃 등으로 망가진 카메라를 정리한다. 다음 get_camera()에서 새로 연다."""
    global camera, camera_closing
    cam, camera = camera, None
    if cam is None:
        return

    def _close():
        # 타임아웃된 캡처 작업이 대기열 맨 앞에 남아 있으면, stop 작업이 그 뒤에서 영원히 기다린다.
        # picamera2가 이 상황(케이블 빠짐 등)을 위해 제공하는 정리 함수
        try:
            cam.cancel_all_and_flush()
        except Exception as e:
            print("camera cancel failed:", repr(e), flush=True)
        for fn in (cam.stop, cam.close):
            try:
                fn()
            except Exception as e:
                print(f"camera {fn.__name__} failed:", repr(e), flush=True)
        print("camera closed", flush=True)

    camera_closing = threading.Thread(target=_close, daemon=True)
    camera_closing.start()


def get_frame():
    with camera_lock:
        if camera_closing is not None and camera_closing.is_alive():
            raise HTTPException(
                status_code=503,
                detail="카메라를 정리하는 중입니다. 계속 이 메시지가 나오면 라즈베리파이를 재부팅하세요.",
            )
        try:
            cam = get_camera()
        except HTTPException:
            raise
        except Exception as e:
            _reset_camera()
            raise HTTPException(status_code=503, detail=f"카메라를 열 수 없습니다: {e}")

        try:
            frame = cam.capture_array(wait=CAPTURE_TIMEOUT)
        except CAPTURE_TIMEOUT_ERRORS:
            _reset_camera()
            raise HTTPException(status_code=503, detail="카메라 프레임 타임아웃 (케이블/전원 확인)")
    return rotate_frame(frame)   # 회전은 lock 밖에서 (다른 요청이 카메라를 기다리지 않게)


async def generate_camera_stream(request):
    interval = 1 / STREAM_FPS
    while True:
        if await request.is_disconnected():
            break

        try:
            frame = await asyncio.to_thread(get_frame)
        except HTTPException as e:
            print("stream stopped:", e.detail)
            break   # 연결을 끊어서 앱의 img error 처리가 동작하게 한다

        h, w = frame.shape[:2]
        s = STREAM_LONG_SIDE / max(w, h)
        small = cv2.resize(frame, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
        ret, buffer = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, STREAM_QUALITY])

        if ret:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )

        await asyncio.sleep(interval)