import cv2
import time
import asyncio
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


def get_camera():
    global camera

    if Picamera2 is None:
        raise HTTPException(status_code=500, detail="Picamera2가 설치되어 있지 않습니다.")

    if camera is None:
        camera = Picamera2()
        config = camera.create_preview_configuration(
            main={"size": (1280, 720), "format": "RGB888"}
        )
        camera.configure(config)
        camera.start()
        time.sleep(1)

    return camera


def get_frame():
    with camera_lock:
        cam = get_camera()
        frame = cam.capture_array()
        return frame

async def generate_camera_stream(request):
    interval = 1 / STREAM_FPS
    while True:
        if await request.is_disconnected():
            break

        frame = await asyncio.to_thread(get_frame)
        small = cv2.resize(frame, STREAM_SIZE)
        ret, buffer = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, STREAM_QUALITY])

        if ret:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )

        await asyncio.sleep(interval)