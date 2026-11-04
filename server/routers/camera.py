import cv2

from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import StreamingResponse

from server.camera.camera import get_camera, generate_camera_stream, get_frame
from server.camera.detector import detect, draw_detections


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
async def camera_stream(request: Request):
    return StreamingResponse(
        generate_camera_stream(request),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store"},
    )


@router.get("/camera/detect")
def camera_detect():
    try:
        frame = get_frame()
        return {"detections": detect(frame)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/camera/detect/image")
def camera_detect_image():
    frame = get_frame().copy()
    dets = detect(frame)
    ok, buf = cv2.imencode(".jpg", draw_detections(frame, dets))
    return Response(content=buf.tobytes(), media_type="image/jpeg")