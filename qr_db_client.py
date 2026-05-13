import requests

# QR 인식 결과(임의 부여)
qr_code = "QR123"

# FastAPI 서버의 QR 조회 API 호출
url = f"http://127.0.0.1:8000/items/{qr_code}"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()

    print("QR 코드:", qr_code)
    print("DB 조회 결과:", data)

    if "destination" in data:
        x = data["destination"]["x"]
        y = data["destination"]["y"]
        print("목적지 좌표:", x, y)
    else:
        print("해당 QR 코드에 대한 목적지 정보가 없습니다.")
else:
    print("API 요청 실패:", response.status_code)