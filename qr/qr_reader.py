import cv2
from pyzbar.pyzbar import decode
import requests

SERVER_URL = "http://taesula.local:8000"

def read_qr_from_camera():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("카메라를 열 수 없습니다.")
        return

    print("QR 코드를 카메라에 비추세요. 종료 버튼 : q")

    while True:
        ret, frame = cap.read()

        if not ret:
            print("프레임을 읽을 수 없습니다.")
            break

        decoded_objects = decode(frame)

        for obj in decoded_objects:
            qr_code = obj.data.decode("utf-8")
            print(f"인식된 QR 코드: {qr_code}")

            try:
                response = requests.get(f"{SERVER_URL}/items/{qr_code}")
                print("DB 조회 결과:")
                print(response.json())

                route_response = requests.get(f"{SERVER_URL}/route/{qr_code}")
                print("경로 탐색 결과:")
                print(route_response.json())

            except requests.exceptions.RequestException as e:
                print(f"서버 요청 오류: {e}")

            cap.release()
            cv2.destroyAllWindows()
            return

        cv2.imshow("QR Reader", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    read_qr_from_camera()