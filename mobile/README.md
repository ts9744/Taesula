# Taesula 모바일 앱

휴대폰 브라우저에서 쓰는 Taesula 관제 앱입니다. 빌드 과정이 없는 순수 HTML·CSS·JavaScript로 되어 있고,
라즈베리파이의 FastAPI 서버(`server/server.py`)가 `/app/` 경로로 함께 제공합니다.

## 화면

| 탭 | 하는 일 | 쓰는 API |
| --- | --- | --- |
| 홈 | 로봇 SIDA 위치·상태(3초마다 갱신), 격자 미니맵, 최근 물품 | `/status`, `/grid-map`, `/locations`, `/items` |
| 인식 | 라즈베리파이 카메라 영상 + QR 자동 인식 → A* 경로 계산 → SIDA 전송. QR 값 직접 입력도 가능 | `/camera/stream`, `/camera/qr`, `/route/{qr}`, `/path` |
| 등록 | 물품 저장 + QR 코드 발급, PNG 저장·공유 | `/items` (POST), `/mobile-api/qr.png` |
| 관리 | 검색, 목적지·이름 수정, 삭제 | `/items` (GET/PUT/DELETE) |
| 격자 | 격자 크기, 장애물·시작점 편집, 목적지 등록, DB 저장·불러오기 | `/grid-map`, `/locations`, `/robot/status` |

## 폴더 구조

```
mobile/
├── index.html              앱 셸 (상단 바 · 화면 · 하단 탭)
├── manifest.webmanifest    홈 화면에 추가할 때 쓰는 앱 정보
├── sw.js                   오프라인용 서비스 워커 (HTTPS에서만 동작)
├── css/app.css             디자인 토큰과 스타일
├── icons/                  앱 아이콘
└── js/
    ├── app.js              해시 라우터 (#/home, #/scan …)
    ├── api.js              서버 API 클라이언트
    ├── ui.js               공통 UI (버튼, 시트, 토스트, 격자 그리기)
    └── screens/            home · scan · register · manage · grid
server/mobile_app.py        /app/ 정적 파일 제공 + QR PNG 생성 API
```

## 실행

1. 라즈베리파이에서 서버 실행

   ```bash
   cd Taesula
   pip install -r requirements.txt
   python server/server.py          # 0.0.0.0:8000 에서 실행
   ```

2. 라즈베리파이 IP 확인: `hostname -I` (예: `192.168.0.20`)
3. 휴대폰을 **같은 Wi-Fi**에 연결하고 브라우저에서 `http://192.168.0.20:8000/app/` 접속
4. 홈 화면에 추가
   - iPhone(Safari): 공유 버튼 → "홈 화면에 추가"
   - Android(Chrome): ⋮ 메뉴 → "홈 화면에 추가"

앱을 서버와 다른 주소에서 열었다면 홈 화면 오른쪽 위 ⚙ 설정에서 서버 주소를 입력합니다.

## 참고

- QR 값은 데스크톱 GUI와 같은 규칙(물품명 = QR 값)을 따릅니다.
- 좌표는 화면과 DB 모두 1부터 시작합니다. (`/route` 응답의 path는 서버 규칙대로 0부터)
- 서비스 워커(오프라인 캐시)는 HTTPS나 localhost에서만 켜집니다. 공장 LAN의 http 주소에서는 꺼진 채로도 앱은 정상 동작합니다.
- 인터넷이 없으면 IBM Plex 글꼴 대신 휴대폰 기본 글꼴로 표시됩니다.
