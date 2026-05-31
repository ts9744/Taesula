import cv2
import time
from threading import Lock
from fastapi import HTTPException

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None


camera = None
camera_lock = Lock()


def get_camera():
    global camera

    if Picamera2 is None:
        raise HTTPException(status_code=500, detail="Picamera2가 설치되어 있지 않습니다.")

    if camera is None:
        camera = Picamera2()
        config = camera.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"}
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


def generate_camera_stream():
    while True:
        frame = get_frame()

        ret, buffer = cv2.imencode(".jpg", frame)

        if not ret:
            continue

        jpg_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpg_bytes + b"\r\n"
        )