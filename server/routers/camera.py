import cv2

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from server.camera.camera import get_camera, generate_camera_stream


router = APIRouter()

qr_detector = cv2.QRCodeDetector()


@router.get("/camera/qr")
def read_qr_from_camera():
    try:
        cam = get_camera()
        frame = cam.capture_array()

        qr_data, points, _ = qr_detector.detectAndDecode(frame)

        if qr_data:
            return {
                "detected": True,
                "qr_code": qr_data
            }

        return {
            "detected": False,
            "qr_code": None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/camera/stream")
def camera_stream():
    return StreamingResponse(
        generate_camera_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
