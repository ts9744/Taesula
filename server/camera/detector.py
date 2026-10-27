"""
Hailo AI HAT+ 기반 YOLOv8n 객체 인식 모듈.

- HEF: models/yolov8n.hef (Hailo-8L 대상, 입력 640x640 RGB, NMS 포함)
- Picamera2 프레임(1280x720, 'RGB888' = 메모리상 BGR)을 받아 letterbox 후 추론
- 결과 좌표는 원본 프레임 픽셀 좌표로 되돌려서 반환

"""
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

try:
    from picamera2.devices import Hailo
except ImportError:
    Hailo = None

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / "models" / "yolov8n.hef"

# 학습할 때 data.yaml 의 names 순서 그대로 적어야 함
CLASS_NAMES = [
    "Box",
    "Cone",
]

SCORE_THRESHOLD = 0.5

_hailo = None
_hailo_lock = Lock()


def get_hailo():
    global _hailo
    if Hailo is None:
        raise RuntimeError("picamera2.devices.Hailo 를 불러올 수 없습니다. hailo-all 설치 여부를 확인하세요.")
    if _hailo is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"HEF 파일이 없습니다: {MODEL_PATH}")
        _hailo = Hailo(str(MODEL_PATH))
    return _hailo


def letterbox(img, new_w, new_h):
    """비율 유지 리사이즈 + 회색(114) 패딩. Ultralytics 학습 전처리와 동일."""
    h, w = img.shape[:2]
    scale = min(new_w / w, new_h / h)
    rw, rh = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(img, (rw, rh), interpolation=cv2.INTER_LINEAR)
    pad_x = (new_w - rw) // 2
    pad_y = (new_h - rh) // 2
    canvas = np.full((new_h, new_w, 3), 114, dtype=np.uint8)
    canvas[pad_y:pad_y + rh, pad_x:pad_x + rw] = resized
    return canvas, scale, pad_x, pad_y


def detect(frame_bgr, threshold=SCORE_THRESHOLD):
    """
    frame_bgr: Picamera2 'RGB888' 로 받은 프레임 (메모리 순서 BGR)
    return: [{"label", "class_id", "score", "box": [x1, y1, x2, y2]}, ...]
    """
    with _hailo_lock:
        hailo = get_hailo()
        model_h, model_w, _ = hailo.get_input_shape()

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        inp, scale, pad_x, pad_y = letterbox(rgb, model_w, model_h)
        outputs = hailo.run(inp)

    h, w = frame_bgr.shape[:2]
    results = []
    # NMS by-class 출력: outputs[class_id] = [[y_min, x_min, y_max, x_max, score], ...] (0~1 정규화)
    for class_id, dets in enumerate(outputs):
        for det in dets:
            score = float(det[4])
            if score < threshold:
                continue
            y0, x0, y1, x1 = det[:4]
            bx0 = (x0 * model_w - pad_x) / scale
            by0 = (y0 * model_h - pad_y) / scale
            bx1 = (x1 * model_w - pad_x) / scale
            by1 = (y1 * model_h - pad_y) / scale
            box = [
                int(np.clip(bx0, 0, w - 1)),
                int(np.clip(by0, 0, h - 1)),
                int(np.clip(bx1, 0, w - 1)),
                int(np.clip(by1, 0, h - 1)),
            ]
            label = CLASS_NAMES[class_id] if class_id < len(CLASS_NAMES) else str(class_id)
            results.append({"label": label, "class_id": class_id, "score": round(score, 3), "box": box})
    return results


def draw_detections(frame_bgr, detections):
    for d in detections:
        x1, y1, x2, y2 = d["box"]
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame_bgr, f'{d["label"]} {d["score"]:.2f}', (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return frame_bgr


if __name__ == "__main__":
    import time
    from picamera2 import Picamera2

    cam = Picamera2()
    cam.configure(cam.create_preview_configuration(main={"size": (1280, 720), "format": "RGB888"}))
    cam.start()
    time.sleep(1)

    for i in range(20):
        frame = cam.capture_array()
        t = time.time()
        dets = detect(frame)
        print(f"[{i}] {(time.time() - t) * 1000:.1f} ms  {dets}")

    cv2.imwrite("detect_test.jpg", draw_detections(frame.copy(), dets))
    print("저장: detect_test.jpg")
    cam.stop()
