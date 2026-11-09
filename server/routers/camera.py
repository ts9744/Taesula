import cv2

from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import StreamingResponse

from server.camera.camera import generate_camera_stream, get_frame
from server.camera.detector import detect, draw_detections


router = APIRouter()

qr_detector = cv2.QRCodeDetector()


@router.get("/camera/qr")
def read_qr_from_camera():
    frame = get_frame()   # lock + 타임아웃 + 자동 재오픈 (실패 시 503)

    try:
        qr_data, points, _ = qr_detector.detectAndDecode(frame)
    except cv2.error as e:
        raise HTTPException(status_code=500, detail=f"QR 디코딩 실패: {e}")

    if qr_data:
        return {"detected": True, "qr_code": qr_data}

    return {"detected": False, "qr_code": None}


@router.get("/camera/stream")
async def camera_stream(request: Request):
    return StreamingResponse(
        generate_camera_stream(request),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store"},
    )


@router.get("/camera/detect")
def camera_detect():
    frame = get_frame()
    try:
        return {"detections": detect(frame)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"객체 인식 실패: {e}")


@router.get("/camera/detect/image")
def camera_detect_image():
    frame = get_frame().copy()
    dets = detect(frame)
    ok, buf = cv2.imencode(".jpg", draw_detections(frame, dets))
    if not ok:
        raise HTTPException(status_code=500, detail="이미지 인코딩 실패")
    return Response(content=buf.tobytes(), media_type="image/jpeg")