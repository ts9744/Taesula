# Taesula

## 📌 프로젝트 개요

본 프로젝트는 QR 기반 물품 인식과 경로 최적화를 적용한 스마트 물류 로봇 시스템을 구현하는 것을 목표로 한다.  
저비용 센서와 경량 알고리즘을 활용하여, 중소규모 공장 및 물류 환경에서도 적용 가능한 자동화 시스템을 설계한다.

---

## 🎯 프로젝트 목표

- QR 기반 물품 인식 및 정보 조회
- A* 기반 경로 탐색 및 D* Lite 기반 재탐색
- 장애물 감지 및 실시간 경로 수정
- 데이터 기반 경로 최적화 (AI)
- 중앙 DB 기반 물류 위치 관리

---

## 🧠 시스템 구조
```
[카메라]
   ↓
QR 인식 (OpenCV)
   ↓
물품 정보 조회 (DB)
   ↓
경로 탐색 (A*, D* Lite)
   ↓
경로 전송 (API)
   ↓
[ESP32 로봇]
   ↓
모터 제어 + 장애물 감지
   ↓
위치 업데이트 → DB 반영
```
---

## 🔧 주요 기능

### 1. QR 코드 기반 물품 인식

- 카메라를 통해 QR 코드 인식
- 물품 ID 추출 및 DB 조회

### 2. 경로 탐색 알고리즘

- A\* 알고리즘을 통한 초기 경로 생성
- Grid 기반 환경 모델링

### 3. 동적 경로 재탐색

- 장애물 감지 시 D\* Lite 알고리즘 적용
- 변경된 환경에 따라 경로 수정

### 4. 장애물 감지

- 초음파 센서를 활용한 거리 측정
- 실시간 장애물 대응

### 5. 데이터 기반 경로 최적화 (AI)

- 이동 거리, 장애물 횟수 등 데이터 수집
- scikit-learn 기반 모델로 경로 평가

### 6. 중앙 관리 시스템

- 물류 위치 DB 반영
- 이동 기록 저장

---

## 🛠 기술 스택

### 💻 Software

- Python
- OpenCV (QR 인식)
- NumPy
- scikit-learn (AI)
- FastAPI (서버)
- SQLite (DB)

### 🤖 Hardware

- C++ (ESP32)
- DC 모터 + 로봇 키트
- 초음파 센서
- USB 카메라

---

## 📂 프로젝트 구조
```
project/
│
├── server/
│ ├── api/
│ ├── db/
│ └── main.py
│
├── algorithm/
│ ├── astar.py
│ ├── dstar_lite.py
│ └── cost_model.py
│
├── robot/
│ ├── esp32_code/
│ └── sensor/
│
├── data/
│ └── logs/
│
└── README.md
```
---

## 🔄 개발 진행 과정

1. A\* 알고리즘 기반 경로 탐색 구현
2. 로봇 기본 이동 및 센서 연동
3. 서버-로봇 통신 구축
4. D\* Lite 기반 재탐색 구현
5. 데이터 수집 및 AI 적용
6. 전체 시스템 통합 및 최적화

---

## 👨‍👩‍👧‍👦 팀원 및 역할

| 이름   | 역할                |
| ------ | ------------------- |
| 김태수 | 통신 및 시스템 통합 |
| 김건우 | 로봇 제어 및 센서   |
| 이민재 | DB 및 서버          |
| 차병철 | AI 및 경로 알고리즘 |

---

## 💡 기대 효과

- 저비용 물류 자동화 시스템 구현
- 동적 환경에서 효율적인 경로 탐색
- 데이터 기반 의사결정 시스템 적용
- 중소규모 공장 적용 가능성 확보

---

## 📈 향후 발전 방향

- 다중 로봇 시스템 확장
- 강화학습 기반 경로 최적화
- 고정밀 위치 인식 기술 적용
- 실제 물류 환경 적용 테스트

---

## 📎 Github Repository

👉 https://github.com/ts9744/Taesula



## 김건우 - 로봇 제어 및 센서 파트 진행 상황

### 1. ESP32 개발 환경 설정

VS Code와 PlatformIO를 이용하여 ESP32 개발 환경을 구성하였다.  
USB-SERIAL CH340(COM3) 포트를 통해 ESP32 보드가 정상적으로 인식되는 것을 확인하였고, 기본 Blink 테스트를 통해 코드 업로드 및 실행이 정상적으로 이루어지는 것을 검증하였다.

### 2. 기본 제어 명령 테스트

Serial Monitor를 이용하여 PC에서 ESP32로 이동 명령을 전송하는 테스트를 진행하였다.

사용한 명령은 다음과 같다.

- F: Forward
- B: Backward
- L: Left
- R: Right
- S: Stop

테스트 결과, 각 명령 입력 시 `moveForward()`, `moveBackward()`, `turnLeft()`, `turnRight()`, `stopMotor()` 함수가 정상적으로 호출되는 것을 확인하였다.  
현재는 실제 모터 연결 전 단계이므로 LED와 Serial 출력을 이용하여 제어 분기 로직을 검증하였다.

### 3. 초음파 센서 연동 준비

초음파 센서를 이용한 장애물 감지 기능을 구현하기 위해 `TRIG_PIN`, `ECHO_PIN`, `OBSTACLE_DISTANCE`를 설정하였다.  
현재 코드에는 거리 측정 함수 `getDistanceCm()`와 장애물 감지 함수 `isObstacleDetected()`를 포함하였다.

추후 초음파 센서를 실제로 연결한 뒤, `D` 명령을 통해 거리값을 확인하고 15cm 이하의 장애물 감지 시 정지 동작이 수행되는지 테스트할 예정이다.

### 4. 다음 구현 예정

- 초음파 센서 실제 연결 및 거리 측정 테스트
- 장애물 감지 시 정지 동작 검증
- 모터 드라이버 연결
- F/B/L/R/S 명령 기반 실제 모터 제어 테스트
- 서버 또는 라즈베리파이에서 전달되는 이동 명령 수신 구조 확장

## 🔍 QR 코드 인식 기능 구동 방법

서버가 실행 중인 상태에서 다른 터미널을 열고 아래 명령어를 실행한다.
```bash
python qr/qr_reader.py
```

QR 코드가 정상 인식되면 카메라에서 읽은 QR 값이 서버 API로 전달되고, /items/{qr_code} 및 /route/{qr_code} 요청 결과가 출력된다.

현재 grid_map 데이터가 DB에 저장되지 않은 경우 /route/{qr_code} 요청에서는 grid map not found가 출력될 수 있다. 이는 지도 데이터 저장 기능이 아직 연결되지 않은 상태에서는 정상적인 응답이다.

### QR 값 입력 규칙

QR Generator에 입력하는 값은 DB의 `items.qr_code` 값과 동일해야 한다.  
현재 테스트 단계에서는 혼동을 줄이기 위해 `items.name`과 `items.qr_code`를 동일한 값으로 등록한다.

예시:

- `items.name`: boxA
- `items.qr_code`: boxA
- QR Generator 입력값: boxA

QR Reader는 QR에서 인식한 문자열을 그대로 서버 API에 전달하므로, QR 내부 값과 DB의 `items.qr_code` 값이 다르면 `/items/{qr_code}` 조회가 실패한다.

## 💻 개발 환경 설정

본 프로젝트는 Python 가상환경에서 실행하는 것을 권장한다.  
라즈베리파이에서 서버 및 QR 인식 기능을 실행하기 전에 아래 순서대로 환경을 설정한다.

### 1. 가상환경 생성 및 활성화

```bash
python -m venv taesula
source taesula/bin/activate
```

### 2. Python 라이브러리 설치

프로젝트에서 사용하는 Python 패키지는 requirements.txt를 통해 설치한다.

```bash
pip install -r requirements.txt
```

### 3. 라즈베리파이 전용 라이브러리 설치

라즈베리파이 카메라 모듈 및 OpenCV 사용을 위해 리눅스 환경에서는 아래 패키지를 추가로 설치한다.

```bash
sudo apt install -y python3-picamera2 python3-opencv
```
python3-picamera2는 라즈베리파이 카메라 모듈을 제어하기 위한 라이브러리이며, python3-opencv는 카메라 프레임 처리 및 QR 코드 인식에 사용된다.
