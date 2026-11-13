# Taesula

## 📌 프로젝트 개요

본 프로젝트는 QR 기반 물품 인식과 경로 최적화를 적용한 스마트 물류 로봇 시스템을 구현하는 것을 목표로 한다.  
저비용 센서와 경량 알고리즘을 활용하여, 중소규모 공장 및 물류 환경에서도 적용 가능한 자동화 시스템을 설계한다.

---

## 🎯 프로젝트 목표

- QR 기반 물품 인식 및 정보 조회
- A* 기반 경로 탐색 및 장애물 감지 시 재탐색
- 장애물 감지 및 실시간 경로 수정
- 데이터 기반 경로 최적화 (AI)
- 중앙 DB 기반 물류 위치 관리

---

## 🧠 시스템 구조

```
[휴대폰 앱 (/app)]  ──HTTP──▶  [FastAPI 서버 (라즈베리파이)]  ◀──HTTP──  [로봇 브리지 (라즈베리파이)]
  QR 인식 · 물품 등록               경로 탐색 (A*)                          server/robot_bridge.py
  격자 편집 · 로봇 상태              장애물 재탐색                                   │
  챗봇 · 알림                        SQLite DB                                  USB 시리얼
                                    카메라 (QR 인식)                                 │
                                                                            [ESP32 로봇 SIDA]
                                                                              메카넘휠 모터 제어
                                                                              초음파 센서
```

- **서버**와 **브리지**는 라즈베리파이에서 각각 따로 실행한다.
- 브리지는 서버에서 다음 명령(`/next-command`)을 받아 ESP32에 시리얼로 전달하고, ESP32의 완료·장애물 보고를 다시 서버로 전달한다.
- ESP32는 Wi-Fi를 쓰지 않고 라즈베리파이와 USB로 연결된다.

---

## 🔄 배송 흐름

1. **QR 인식**: 앱의 인식 탭에서 카메라로 QR을 읽거나 QR 값을 직접 입력한다.
2. **경로 계산**: 서버가 DB에서 물품의 목적지를 찾고, 로봇의 현재 위치에서 A*로 경로를 계산한다.  
   물품 상태 `moving`, 로봇 상태 `moving`으로 바뀐다.
3. **이동**: 브리지가 `/next-command`로 명령을 받아 ESP32에 보낸다. 같은 방향 명령은 묶어서 보낸다 (예: `forward 3`).  
   이동이 끝날 때마다 서버가 DB의 로봇 위치를 갱신한다.
4. **도착**: 남은 명령이 없으면 물품 상태 `arrived`, 로봇 상태 `idle`로 바뀌고 앱에 도착 알림이 뜬다.
5. **자동 복귀**: 도착 10초 뒤 시작점으로 자동 복귀한다. 앱 홈의 "시작점으로 복귀" 버튼으로도 복귀할 수 있다.
6. **대기열**: 배송·복귀 중에 인식된 QR은 대기열(`queued`)에 들어가고, 시작점에 돌아온 뒤 10초 후 순서대로 출발한다.

### 장애물 처리

- 로봇이 장애물을 감지해 보고하면, 서버가 그 칸을 막힌 칸으로 표시하고 현재 위치에서 경로를 다시 계산한다.
- 막힌 칸은 30초 뒤 자동으로 풀린다. 길이 없으면 10초 간격으로 최대 4번 다시 시도한다.
- 4번 모두 실패하면 앱 홈 화면에 "다시 시도" 버튼이 나타난다 (사람이 장애물을 치운 뒤 누른다).
- 앱 홈 미니맵에서 칸을 눌러 장애물을 직접 표시·해제할 수 있다 (직접 표시한 칸은 자동으로 풀리지 않는다).

> 🚧 **작성 예정 (로봇 파트)**: 센서 구성, 감지 방식과 감지 거리, 칸 크기·모터 동작 시간 등 실측 수치

### 이동 명령 기준 (메카넘휠 횡이동)

로봇은 메카넘휠로 회전 없이 횡이동한다. 항상 격자의 **위쪽(북쪽)을 바라보도록 시작점에 놓는다.**

```text
forward  : 위로 한 칸     (y - 1)
backward : 아래로 한 칸   (y + 1)
left     : 왼쪽으로 한 칸 (x - 1)
right    : 오른쪽으로 한 칸 (x + 1)
stop     : 정지 (경로의 끝)
```

---

## 🔧 주요 기능

### 1. QR 코드 기반 물품 인식

- 라즈베리파이 카메라로 QR 코드 인식 (앱 인식 탭)
- 물품 QR 값으로 DB 조회 후 바로 배송 시작

### 2. 경로 탐색 알고리즘

- A\* 알고리즘을 통한 경로 생성
- Grid 기반 환경 모델링 (앱 격자 탭 또는 데스크톱 GUI에서 편집)

### 3. 동적 경로 재탐색

- 장애물 감지 시 막힌 칸을 반영해 A\*로 경로 재계산
- 막힌 칸 자동 해제와 재시도, 사람 개입("다시 시도") 지원

### 4. 장애물 감지

- 초음파 센서를 활용한 거리 측정
- 감지 시 서버에 보고하고 우회 경로로 이동

### 5. 데이터 기반 경로 최적화 (AI)

- 이동 거리, 장애물 횟수 등 데이터 수집
- scikit-learn 기반 모델로 경로 평가

### 6. 중앙 관리 시스템

- 물품·목적지·로봇 위치를 SQLite DB로 관리
- 휴대폰 앱으로 로봇 상태 확인, 물품 등록·관리, 알림

### 7. 챗봇

- 로컬 LLM(Ollama)으로 자연어 물품 조회와 로봇 제어 (앱 챗봇 탭)

---

## 🛠 기술 스택

### 💻 Software

- Python
- FastAPI (서버), SQLite (DB)
- OpenCV (QR 인식)
- pyserial (ESP32 시리얼 통신)
- Ollama (챗봇)
- HTML · CSS · JavaScript (모바일 웹앱)
- scikit-learn (AI)

### 🤖 Hardware

- Raspberry Pi 5 + 카메라 모듈
- ESP32 (C++, PlatformIO)
- 메카넘휠 + DC 모터
- 초음파 센서

---

## 📂 프로젝트 구조

```
Taesula/
├── server/                     FastAPI 서버 (라즈베리파이)
│   ├── server.py               서버 진입점 · API 키 인증
│   ├── robot_bridge.py         서버 ↔ ESP32 시리얼 브리지 (따로 실행)
│   ├── state.py                배송 진행 상태 (메모리)
│   ├── database.py             DB 연결
│   ├── replan_logic.py         장애물 재탐색 계산
│   ├── routers/                API (기능별)
│   │   ├── route.py            QR → 경로 계산 · 대기열
│   │   ├── command.py          명령 전달 (/next-command, /command/done)
│   │   ├── obstacle.py         장애물 보고 · 재탐색 · 재시도
│   │   ├── home.py             시작점 복귀
│   │   ├── robot.py            로봇 상태 · ESP32 연결 상태
│   │   ├── items.py            물품
│   │   ├── locations.py        목적지
│   │   ├── grid_map.py         격자 지도
│   │   ├── camera.py           카메라 · QR 인식
│   │   ├── system.py           전체 상태 (/status)
│   │   └── mobile_app.py       앱 파일 제공 (/app)
│   ├── schemas/                요청 형식
│   ├── camera/                 카메라 · 객체 인식
│   └── chatbot/                챗봇 (Ollama)
├── algorithm/astar.py          A* 경로 탐색
├── mobile/                     휴대폰 웹앱 (mobile/README.md 참고)
├── factory/                    데스크톱 관리 GUI
├── Taesula_Robot_Control/      ESP32 펌웨어 (PlatformIO)
├── models/                     객체 인식 모델
├── db_init.py                  DB 테이블 생성
└── requirements.txt
```

---

## 🗄 DB 구조

| 테이블 | 내용 | 주요 칼럼 |
| --- | --- | --- |
| `locations` | 목적지(구역) | `id`, `zone_name`(중복 불가), `x`, `y` |
| `items` | 물품 | `id`, `name`, `qr_code`(중복 불가), `destination_id`(→ locations.id), `status` |
| `robot_status` | 로봇 현재 위치·상태 | `current_x`, `current_y`, `status` |
| `grid_map` | 격자 지도 (1개) | `rows`, `cols`, `raw_grid`, `pathfinding_grid` |

- 좌표는 DB와 앱 모두 **1부터** 센다.
- 물품 상태: `waiting`(대기) · `queued`(대기열) · `moving`(이동 중) · `arrived`(도착)
- 로봇 상태: `idle` · `moving` · `obstacle_detected`
- 진행 중인 경로, 막힌 칸, 대기열은 DB가 아니라 서버 메모리에 있다. **서버를 재시작하면 사라진다.**

---

## 💻 개발 환경 설정

본 프로젝트는 Python 가상환경에서 실행하는 것을 권장한다.

### 1. 가상환경 생성 및 활성화

```bash
python -m venv taesula
source taesula/bin/activate
```

### 2. Python 라이브러리 설치

```bash
pip install -r requirements.txt
```

### 3. 라즈베리파이 전용 라이브러리 설치

```bash
sudo apt install -y python3-picamera2 python3-opencv
```

python3-picamera2는 라즈베리파이 카메라 모듈을 제어하기 위한 라이브러리이며, python3-opencv는 카메라 프레임 처리 및 QR 코드 인식에 사용된다.

### 4. DB 초기화 (처음 한 번)

레포 최상위 폴더에서 실행한다.

```bash
python db_init.py
```

---

## ▶️ 실행 방법

### 1. 환경변수

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `TAESULA_API_KEY` | 브리지 사용 시 필수 | API 인증 키. 서버와 브리지에 **같은 값**을 넣는다 |
| `TAESULA_ADMIN_KEY` | 시연 시 권장 | 관리자 키. 설정하면 격자 지도 저장, 목적지 추가·수정·삭제에 이 키가 필요하다. 앱은 홈 화면 설정의 **관리자 키** 칸에, 공장 GUI는 `factory/.env`에 같은 값을 넣는다. 비워 두면 누구나 수정할 수 있다 |
| `TAESULA_ESP32_PORT` | 선택 | ESP32 시리얼 포트 (기본: `/dev/serial/by-id/usb-Silicon_Labs_CP2102_...`) |
| `TAESULA_ENABLE_DOCS` | 선택 | `1`이면 `/docs` API 문서 화면을 켠다 (기본 꺼짐) |
| `OLLAMA_HOST`, `OLLAMA_MODEL` | 선택 | 챗봇 설정 (아래 챗봇 항목 참고) |

```bash
export TAESULA_API_KEY=<팀에서 정한 키>
```

### 2. 서버 실행 (터미널 1)

레포 최상위 폴더에서 실행한다.

```bash
python -m server.server
```

`0.0.0.0:8000`에서 실행된다.

### 3. 로봇 브리지 실행 (터미널 2)

ESP32를 라즈베리파이 USB에 연결한 뒤 실행한다.

```bash
python server/robot_bridge.py
```

- ESP32가 연결되어 있지 않으면 연결될 때까지 기다린다. 연결 상태는 `GET /robot/esp32`로 확인할 수 있다.
- 이동 중 오류로 브리지가 멈추면, 로봇을 시작점에 직접 놓고 앱 격자 탭의 **"로봇을 시작점에 두기"** 를 누르면 다시 동작한다.

### 4. 앱 접속

| 접속 위치 | 주소 | API 키 |
| --- | --- | --- |
| 같은 Wi-Fi의 휴대폰·노트북 | `http://<라즈베리파이 IP>:8000/app/` | 필요 없음 |
| 라즈베리파이 자신 (localhost) · 외부 공개 주소(Funnel) | `http://localhost:8000/app/?key=<API 키>` | 필요 |

- 라즈베리파이 IP는 `hostname -I`로 확인한다.
- `?key=`를 붙여 한 번 열면 앱이 키를 저장한다.
- 앱 화면별 설명은 [`mobile/README.md`](mobile/README.md)를 참고한다.

### QR 값 입력 규칙

QR에 넣는 값은 DB의 `items.qr_code` 값과 같아야 한다. 혼동을 줄이기 위해 `items.name`과 `items.qr_code`를 같은 값으로 등록한다 (예: `boxA`).  
앱의 등록 탭에서 물품을 저장하면 QR 코드 이미지가 함께 발급된다.

---

## 📡 주요 API

| 구분 | API | 설명 |
| --- | --- | --- |
| 배송 | `GET /route/{qr_code}` | QR로 경로 계산 후 배송 시작 (진행 중이면 대기열) |
| 로봇 명령 | `GET /next-command` | 다음 이동 명령 (`{"direction": "forward", "steps": 3}`) |
| | `POST /command/done` | 도착(stop) 완료 보고 |
| 장애물 | `POST /robot/obstacle` | 장애물 보고 → 재탐색 |
| | `GET /robot/obstacles` | 막힌 칸 · 남은 경로 · 재탐색 상태 |
| | `POST /robot/manual-block` | 앱에서 장애물 직접 표시·해제 |
| | `POST /robot/resume` | 다시 시도 (막힌 칸 풀고 경로 재계산) |
| 복귀 | `POST /robot/return-home` | 시작점으로 복귀 |
| | `POST /robot/place-at-start` | 로봇을 시작점에 놓았을 때 상태 초기화 |
| 상태 | `GET /status` | 로봇 상태 · 남은 경로 · 대기열 |
| | `GET /robot/esp32` | ESP32 연결 상태 |
| 데이터 | `/items`, `/locations`, `/grid-map` | 물품 · 목적지 · 격자 지도 |
| 카메라 | `GET /camera/stream`, `GET /camera/qr` | 카메라 영상 · QR 인식 |
| 챗봇 | `POST /chat` | 자연어 요청 |

전체 목록은 `TAESULA_ENABLE_DOCS=1`로 서버를 실행한 뒤 `/docs`에서 확인할 수 있다.

---

## 🤖 챗봇(자연어 제어 / 재고 조회) 설정

챗봇은 [Ollama](https://ollama.com)로 로컬에서 돌아가는 LLM을 사용해 자연어 요청을 물품 조회·로봇 제어 API 호출로 변환한다. 라즈베리파이5(4GB) 기준으로도 무리 없이 돌아가도록 기본 모델은 3B급 경량 모델을 사용한다.  
앱의 **챗봇 탭**에서 사용할 수 있다.

### 1. Ollama 설치 및 모델 준비

```bash
# https://ollama.com 에서 설치 후
ollama pull qwen2.5:3b-instruct
```

한국어 대신 Meta Llama 계열을 쓰고 싶다면 `ollama pull llama3.2:3b` 후 환경변수 `OLLAMA_MODEL=llama3.2:3b`로 지정하면 된다.

### 2. 환경변수 (선택)

서버를 실행하는 터미널에서 지정한다. (지정하지 않으면 기본값 사용)

```bash
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=qwen2.5:3b-instruct
```

### 3. `/chat` API

```bash
curl -X POST http://<라즈베리파이 IP>:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "boxA 재고 상태 알려줘"}'
```

- 요청: `{"session_id": "<대화를 구분하는 임의의 문자열>", "message": "<자연어 요청>"}`
- 응답: `{"reply": "<챗봇의 한국어 답변>"}`

같은 `session_id`로 계속 요청하면 이전 대화 맥락이 유지된다.

---

## 🔄 개발 진행 과정

1. A\* 알고리즘 기반 경로 탐색 구현
2. 로봇 기본 이동 및 센서 연동
3. 서버-로봇 통신 구축 (HTTP → USB 시리얼 브리지로 변경)
4. 서버 구조 리팩터링 (기능별 router 분리)
5. 휴대폰 관제 앱 · 챗봇 · 알림
6. 배송 진행 추적, 자동 복귀, 배송 대기열
7. 장애물 감지 및 재탐색
8. 데이터 수집 및 AI 적용 (예정)
9. 전체 시스템 통합 및 최적화

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

---

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
