import cv2
import time
import asyncio
import concurrent.futures
from threading import Lock
from fastapi import HTTPException

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None


camera = None
camera_lock = Lock()
STREAM_SIZE = (480, 270)   # 스트림 해상도 (QR 인식은 원본 1280x720 그대로 사용)
STREAM_QUALITY = 60        # JPEG 품질 (기본 95)
STREAM_FPS = 15            # 초당 프레임 수
CAPTURE_TIMEOUT = 3        # 프레임 대기 최대 시간(초)

# Python 3.11+ 에서는 둘이 같은 클래스지만, 버전 차이에 대비해 둘 다 잡는다
CAPTURE_TIMEOUT_ERRORS = (TimeoutError, concurrent.futures.TimeoutError)


def get_camera():
    global camera

    if Picamera2 is None:
        raise HTTPException(status_code=500, detail="Picamera2가 설치되어 있지 않습니다.")

    if camera is None:
        cam = Picamera2()
        config = cam.create_preview_configuration(
            main={"size": (1280, 720), "format": "RGB888"}
        )
        cam.configure(config)
        cam.start()
        time.sleep(1)
        camera = cam   # 초기화가 끝난 뒤에만 전역에 넣는다

    return camera


def _reset_camera():
    """타임아웃 등으로 망가진 카메라를 닫는다. 다음 get_camera()에서 새로 연다."""
    global camera
    cam, camera = camera, None
    if cam is None:
        return
    try:
        cam.stop()
    except Exception as e:
        print("camera stop failed:", e)
    try:
        cam.close()
    except Exception as e:
        print("camera close failed:", e)


def get_frame():
    with camera_lock:
        try:
            cam = get_camera()
        except HTTPException:
            raise
        except Exception as e:
            _reset_camera()
            raise HTTPException(status_code=503, detail=f"카메라를 열 수 없습니다: {e}")

        try:
            return cam.capture_array(wait=CAPTURE_TIMEOUT)
        except CAPTURE_TIMEOUT_ERRORS:
            _reset_camera()
            raise HTTPException(status_code=503, detail="카메라 프레임 타임아웃 (케이블/전원 확인)")


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

        small = cv2.resize(frame, STREAM_SIZE)
        ret, buffer = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, STREAM_QUALITY])

        if ret:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )

        await asyncio.sleep(interval)