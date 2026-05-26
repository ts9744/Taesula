import cv2
from fastapi import HTTPException

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None


camera = None

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

    return camera