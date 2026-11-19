#include <Arduino.h>

// =====================================================================
// Taesula ESP32 - 초음파 4방향 + 이동 중 stop + 엔코더 측정 (2026-11-15)
//
// [엔코더]
//   - 바퀴 4개 C1 펄스를 셈 (방향은 모름, 돈 양만)
//   - 이동 끝날 때마다 DONE/OBSTACLE 바로 앞에 출력:
//       ENC FL 820 FR 905 RL 760 RR 910
//       ENC% FL 90 FR 99 RL 84 RR 100
//       SUGGEST FL_TRIM 0.93 FR_TRIM 0.84 RL_TRIM 1.00 RR_TRIM 0.83
//   - enc / enc reset : 손으로 바퀴 돌려서 배선 확인
//   - 실제 주행 땐 PRINT_ENCODER = false 추천
//
// 기존 main_motor_test.cpp 에서 바뀐 점
//   1) 초음파 4개: 가는 방향의 센서 1개만 켜서 감시
//        forward -> 앞 / backward -> 뒤 / left -> 왼쪽 / right -> 오른쪽
//   2) 이동 중에도 시리얼을 읽음: "stop" 이 오면 바로 정지
//        (AI HAT 카메라가 장애물을 보면 라즈베리파이가 stop 을 보내는 용도)
//   3) dist  : 4개 거리를 한 줄로 출력
//      scan  : 4개 거리를 0.2초마다 20번 출력 (센서 고정 위치 확인용, stop 으로 중단)
//   4) sonar on / sonar off : 이동 중 감지 켜기/끄기 (리셋하면 다시 ON)
//
// 모터 핀 / INV / TRIM / 속도 / 이동 시간은 기존 코드와 같음
// 라즈베리파이 통신 형식(DONE / OBSTACLE)도 같음
// =====================================================================

// 테스트용 LED
const int LED_PIN = 15;   // 2026-11-15: GPIO2 를 FL_IN2 로 쓰게 돼서 LED 표시는 빈 핀(15)으로 (실제 LED 없음)

// ===============================
// 초음파 센서 4개
// 번호: 0 = 앞, 1 = 왼쪽, 2 = 뒤, 3 = 오른쪽
// ECHO 는 모두 분압(저항) 거쳐서 들어옴
// ===============================
const int SONAR_COUNT = 4;
const int S_FRONT = 0;
const int S_LEFT  = 1;
const int S_BACK  = 2;
const int S_RIGHT = 3;

const char* SONAR_NAME[SONAR_COUNT] = {"front", "left", "back", "right"};
const int   TRIG_PINS[SONAR_COUNT]  = {5,  4,  21, 13};   // P5, P4, P21, P13
const int   ECHO_PINS[SONAR_COUNT]  = {18, 34, 39, 35};   // P18, P34, SVN(39), P35

// ===============================
// 엔코더 C1 (VCC = 3.3V 레일, GND = − 레일, C2 는 안 씀)
// 순서: FL, FR, RL, RR
// ===============================
const int ENC_COUNT = 4;
const char* WHEEL_NAME[ENC_COUNT] = {"FL", "FR", "RL", "RR"};
const int   ENC_PINS[ENC_COUNT]   = {27, 33, 14, 36};   // P27, P33, P14, SVP(36)
const unsigned long ENC_MIN_GAP_US = 200;                // 너무 짧은 간격 펄스는 노이즈로 무시
const bool PRINT_ENCODER = true;                         // 실제 주행 땐 false 추천

volatile unsigned long encCount[ENC_COUNT] = {0, 0, 0, 0};
volatile unsigned long encLastUs[ENC_COUNT] = {0, 0, 0, 0};

void IRAM_ATTR encTick(int i) {
  unsigned long now = micros();
  if (now - encLastUs[i] >= ENC_MIN_GAP_US) {
    encCount[i]++;
    encLastUs[i] = now;
  }
}
void IRAM_ATTR encIsrFL() { encTick(0); }
void IRAM_ATTR encIsrFR() { encTick(1); }
void IRAM_ATTR encIsrRL() { encTick(2); }
void IRAM_ATTR encIsrRR() { encTick(3); }

// ===============================
// ZK-BM1 #1 : 앞바퀴
// ===============================
const int FL_IN1 = 25;
const int FL_IN2 = 2;    // 2026-11-15: P26 경로 고장 -> P2 (ESP32 빵판 j21) 로 옮김

const int FR_IN1 = 32;
const int FR_IN2 = 19;

// ===============================
// ZK-BM1 #2 : 뒷바퀴
// ===============================
// 드라이버 #2 출력에서 뒤 모터 좌우가 바뀌어 연결되어 코드에서 맞바꿈
//   P22/P23 (드라이버 #2 IN3/IN4) -> 뒤-왼쪽 바퀴
//   P16/P17 (드라이버 #2 IN1/IN2) -> 뒤-오른쪽 바퀴
const int RL_IN1 = 22;
const int RL_IN2 = 23;

const int RR_IN1 = 16;
const int RR_IN2 = 17;

// ===============================
// 모터 방향 보정 (바퀴가 반대로 돌면 그 모터만 true/false 바꾸기)
// ===============================
const bool FL_INV = false;   // 2026-11-12: 재배선 후 FL이 거꾸로 돌아서 true -> false
const bool FR_INV = true;
const bool RL_INV = false;
const bool RR_INV = true;

// ===============================
// 이동 설정
// ===============================
const unsigned long FORWARD_RUN_MS = 1000;   // 1칸 이동 시간 (전진/후진)
const unsigned long STRAFE_RUN_MS  = 1000;   // 1칸 이동 시간 (좌/우)

const int MOTOR_SPEED  = 255;
const int STRAFE_SPEED = 255;

// 바퀴별 속도 보정 (1.00 = 그대로, 0.95 = 5% 느리게)
const float FL_TRIM = 0.91;   // 2026-11-15: 엔코더 측정으로 RL(가장 느림)에 맞춤
const float FR_TRIM = 0.75;   // 2026-11-15 새 드라이버 후 미세조정
const float RL_TRIM = 1.00;
const float RR_TRIM = 0.73;

// ===============================
// 좌우 이동(left/right) 전용 보정 - 직진 값과 따로
//   left/right 2 하고 나오는 SUGGEST(strafe) 값을 여기에 넣기
//   눈으로 맞출 때:
//     right 가 오른쪽 '위(앞)'로 뜨고 left 가 왼쪽 '아래(뒤)'로 처지면 -> SFL, SRR 을 0.03 씩 낮추기
//     right 가 오른쪽 '아래(뒤)'로 처지고 left 가 왼쪽 '위(앞)'로 뜨면 -> SFR 을 0.03 씩 낮추기
//   (RL 은 이미 가장 느려서 1.00 고정)
// ===============================
const float SFL_TRIM = 0.81;   // 2026-11-15: 엔코더 + 눈으로 맞춤
const float SFR_TRIM = 0.81;
const float SRL_TRIM = 1.00;
const float SRR_TRIM = 0.87;

// ===============================
// 왼쪽 이동(left) 전용 보정 - right 는 위 S... 값, left 는 아래 L... 값
//   left 가 왼쪽 '아래(뒤)'로 처지면 -> LFL, LRR 을 0.02~0.03 씩 낮추기
//   left 가 왼쪽 '위(앞)'로 뜨면     -> LFL, LRR 을 0.02~0.03 씩 올리기
// ===============================
const float LFL_TRIM = 0.78;
const float LFR_TRIM = 0.78;
const float LRL_TRIM = 1.00;
const float LRR_TRIM = 0.80;

// ===============================
// 이동 중 장애물 감지
// ===============================
const float STOP_DISTANCE_CM = 10.0;            // 이 거리 이하면 정지
const unsigned long SENSOR_INTERVAL_MS = 50;    // 이동 중 측정 간격
const int CONFIRM_COUNT = 2;                    // 연속 2번 이하일 때만 정지 (튀는 값 무시)
const bool PRINT_DISTANCE = true;               // 이동 중 거리 출력 (테스트용, 실제 주행 땐 false 추천)
const unsigned long MOVE_TIMEOUT_US = 6000;     // 이동 중엔 약 1m 까지만 측정 (빨리 끝나게)
const unsigned long DIST_TIMEOUT_US = 30000;    // dist/scan 땐 약 5m 까지

// 멈출 때 브레이크 (IN1=IN2=HIGH) 거는 시간. 짐이 미끄러지면 80, 그래도 틀어지면 250
// 멈추는 방법 (2026-11-15 변경)
//   1) RAMP_MS 동안 4바퀴를 같은 비율로 같이 감속 (서는 시점을 맞춤)
//   2) 그 다음 BRAKE_MS 동안 짧게 브레이크
//   멈출 때 아직 틀어지면 RAMP_MS 를 250~300 으로, 짐이 쏠리면 150 으로
const unsigned long RAMP_MS  = 200;
const int           RAMP_STEPS = 10;
const unsigned long BRAKE_MS = 250;            // 감속 후 브레이크 (이미 거의 멈춘 상태라 드라이버 부담 작음)
const unsigned long EMERGENCY_BRAKE_MS = 120;  // 장애물/stop 급정지 때 (감속 없이 바로라 짧게)
bool motorsRunning = false;
float speedScale = 1.0;               // 감속 중에만 1.0 -> 0 으로 내려감
void (*currentAction)() = nullptr;    // 지금 실행 중인 이동 (감속할 때 다시 호출)

bool sonarEnabled = true;   // sonar off 로 끌 수 있음. 리셋하면 다시 ON

// ===============================
// [2026-11-15] 엔코더 실시간 속도 맞추기 (sync)
//   이동 중 SYNC_MS 마다 4바퀴 누적 펄스를 비교해서
//   뒤처진 바퀴는 PWM 올리고, 앞선 바퀴는 내림 -> 4바퀴가 같은 양만큼 돌게
//   - sync on / sync off 명령으로 켜고 끄기 (리셋하면 ON)
//   - 엔코더 하나라도 안 들어오면 그 이동은 자동으로 sync 끔 (SYNC OFF 출력)
//   - 흔들리면(바퀴가 번갈아 울컥) SYNC_KP 를 0.5 로, 효과가 약하면 1.5 로
// ===============================
bool syncEnabled = true;
const unsigned long SYNC_MS       = 50;    // 보정 주기
const unsigned long SYNC_START_MS = 150;   // 출발 직후는 보정 안 함 (가속 구간)
const float SYNC_KP     = 1.0;             // 펄스 1개 차이당 PWM 몇 만큼 보정
const int   SYNC_MAX_ADJ = 60;             // 보정 최대치 (PWM)
int  syncAdj[4] = {0, 0, 0, 0};            // 바퀴별 보정값 FL, FR, RL, RR
bool syncActive = false;

String lineBuf;       // 평소 명령 받는 버퍼
String moveBuf;       // 이동 중 명령 받는 버퍼
String pendingLine;   // 이동 중에 들어온 stop 외 명령 (이동 끝나고 처리)

enum RunResult { RUN_DONE, RUN_OBSTACLE, RUN_STOPPED };


// ===============================
// 함수 선언
// ===============================
void driveMotor(int in1, int in2, bool forward, bool inverted, int speed);
int trimmed(int base, float trim);
void stopMotorPair(int in1, int in2);
void stopMotor();

void moveForward();
void moveBackward();
void strafeLeft();
void strafeRight();

RunResult runTimed(void (*action)(), unsigned long ms, int sensor,
                   unsigned long &ranMs, float &stopDist);
bool pollStopDuringMove();
void handleLine(String line);

float readDistanceCm(int sensor, unsigned long timeoutUs);
void printAllDistances();

void encReset();
void printEncoder(int mode);   // 0 = 전진/후진, 1 = right, 2 = left


// ===============================
// SETUP
// ===============================
void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);

  for (int i = 0; i < SONAR_COUNT; i++) {
    pinMode(TRIG_PINS[i], OUTPUT);
    digitalWrite(TRIG_PINS[i], LOW);
    pinMode(ECHO_PINS[i], INPUT);
  }

  // 엔코더 (GPIO36 은 내부 풀업 없음: RR 이 계속 0 이면 a9 ↔ 3.3V 레일에 10kΩ)
  for (int i = 0; i < ENC_COUNT; i++) {
    pinMode(ENC_PINS[i], (ENC_PINS[i] >= 34) ? INPUT : INPUT_PULLUP);
  }
  attachInterrupt(digitalPinToInterrupt(ENC_PINS[0]), encIsrFL, RISING);
  attachInterrupt(digitalPinToInterrupt(ENC_PINS[1]), encIsrFR, RISING);
  attachInterrupt(digitalPinToInterrupt(ENC_PINS[2]), encIsrRL, RISING);
  attachInterrupt(digitalPinToInterrupt(ENC_PINS[3]), encIsrRR, RISING);

  pinMode(FL_IN1, OUTPUT);
  pinMode(FL_IN2, OUTPUT);
  pinMode(FR_IN1, OUTPUT);
  pinMode(FR_IN2, OUTPUT);
  pinMode(RL_IN1, OUTPUT);
  pinMode(RL_IN2, OUTPUT);
  pinMode(RR_IN1, OUTPUT);
  pinMode(RR_IN2, OUTPUT);

  stopMotor();

  delay(300);

  Serial.println("READY (sonar4 + encoder + sync, sonar ON, sync ON)");
}


// ===============================
// LOOP
// ===============================
void loop() {
  // 이동 중에 들어왔던 명령이 있으면 먼저 처리
  if (pendingLine.length() > 0) {
    String l = pendingLine;
    pendingLine = "";
    handleLine(l);
  }

  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n') {
      lineBuf.trim();
      if (lineBuf.length() > 0) {
        String l = lineBuf;
        lineBuf = "";
        handleLine(l);
      }
      lineBuf = "";
    }
    else if (c != '\r') {
      lineBuf += c;
      if (lineBuf.length() > 64) {
        lineBuf = "";
      }
    }
  }
}


// ===============================
// 명령 처리
//
// forward 3 / backward 1 / left 2 / right 1   (라즈베리파이가 보내는 명령)
// stop
// dist            4방향 거리 한 번
// scan            4방향 거리 0.2초마다 20번 (stop 으로 중단)
// sonar on / off  이동 중 감지 켜기/끄기
// fl / fr / rl / rr   바퀴 하나만 1초 전진 테스트
// ===============================
void handleLine(String line) {

  int sp = line.indexOf(' ');

  String dir = (sp == -1) ? line : line.substring(0, sp);
  String arg = (sp == -1) ? "" : line.substring(sp + 1);
  arg.trim();

  dir.toLowerCase();
  arg.toLowerCase();

  int steps = (arg.length() == 0) ? 1 : arg.toInt();


  // -------------------------------
  // 정지
  // -------------------------------
  if (dir == "stop") {
    stopMotor();
    Serial.println("DONE stop 0");
    return;
  }


  // -------------------------------
  // 초음파 감지 켜기/끄기
  // -------------------------------
  if (dir == "sync") {
    if (arg == "off") syncEnabled = false;
    else if (arg == "on") syncEnabled = true;
    Serial.print("SYNC ");
    Serial.println(syncEnabled ? "ON" : "OFF");
    return;
  }


  if (dir == "sonar") {
    if (arg == "off") sonarEnabled = false;
    else if (arg == "on") sonarEnabled = true;
    Serial.print("SONAR ");
    Serial.println(sonarEnabled ? "ON" : "OFF");
    return;
  }


  // -------------------------------
  // 엔코더: enc (누적값) / enc reset (0으로)
  // -------------------------------
  if (dir == "enc") {
    if (arg == "reset") encReset();
    Serial.print("ENC");
    for (int i = 0; i < ENC_COUNT; i++) {
      Serial.print(' ');
      Serial.print(WHEEL_NAME[i]);
      Serial.print(' ');
      Serial.print((unsigned long)encCount[i]);
    }
    Serial.println();
    return;
  }


  // -------------------------------
  // 4방향 거리 한 번
  // -------------------------------
  if (dir == "dist") {
    printAllDistances();
    return;
  }


  // -------------------------------
  // 4방향 거리 연속 (센서 고정 위치 확인용)
  // -------------------------------
  if (dir == "scan") {
    for (int k = 0; k < 20; k++) {
      printAllDistances();
      unsigned long t = millis();
      while (millis() - t < 200) {
        if (pollStopDuringMove()) {
          Serial.println("DONE stop 0");
          return;
        }
      }
    }
    Serial.println("DONE scan");
    return;
  }


  // -------------------------------
  // 바퀴 하나만 테스트: fl / fr / rl / rr
  // -------------------------------
  if (dir == "fl" || dir == "fr" || dir == "rl" || dir == "rr") {

    int in1, in2;
    bool inv;
    float trim;

    if (dir == "fl")      { in1 = FL_IN1; in2 = FL_IN2; inv = FL_INV; trim = FL_TRIM; }
    else if (dir == "fr") { in1 = FR_IN1; in2 = FR_IN2; inv = FR_INV; trim = FR_TRIM; }
    else if (dir == "rl") { in1 = RL_IN1; in2 = RL_IN2; inv = RL_INV; trim = RL_TRIM; }
    else                  { in1 = RR_IN1; in2 = RR_IN2; inv = RR_INV; trim = RR_TRIM; }

    Serial.print("TEST ");
    Serial.print(dir);
    Serial.print(" (GPIO ");
    Serial.print(in1);
    Serial.print("/");
    Serial.print(in2);
    Serial.println(") forward 1s");

    digitalWrite(LED_PIN, HIGH);
    driveMotor(in1, in2, true, inv, trimmed(MOTOR_SPEED, trim));
    delay(1000);
    stopMotor();

    Serial.println("DONE test");
    return;
  }


  if (steps < 1) {
    steps = 1;
  }


  // -------------------------------
  // 이동 명령: 방향에 맞는 센서 1개 고르기
  // -------------------------------
  void (*action)() = nullptr;
  unsigned long runMs = 0;
  int sensor = -1;

  if (dir == "forward") {
    action = moveForward;  runMs = FORWARD_RUN_MS; sensor = S_FRONT;
  }
  else if (dir == "backward") {
    action = moveBackward; runMs = FORWARD_RUN_MS; sensor = S_BACK;
  }
  else if (dir == "left") {
    action = strafeLeft;   runMs = STRAFE_RUN_MS;  sensor = S_LEFT;
  }
  else if (dir == "right") {
    action = strafeRight;  runMs = STRAFE_RUN_MS;  sensor = S_RIGHT;
  }
  else {
    Serial.println("ERR unknown " + line);
    return;
  }

  if (!sonarEnabled) {
    sensor = -1;
  }


  // -------------------------------
  // steps 칸을 멈추지 않고 한 번에 이동
  // -------------------------------
  unsigned long ranMs = 0;
  float stopDist = -1;

  encReset();
  RunResult r = runTimed(action, runMs * steps, sensor, ranMs, stopDist);

  if (PRINT_ENCODER) {
    printEncoder(dir == "right" ? 1 : (dir == "left" ? 2 : 0));
  }

  unsigned long cellsDone = ranMs / runMs;
  unsigned long msInCell  = ranMs % runMs;

  if (r == RUN_OBSTACLE) {
    // 형식: OBSTACLE <방향> <끝낸 칸 수> <이번 칸에서 움직인 ms> <거리 cm>
    Serial.println();
    Serial.print("OBSTACLE ");
    Serial.print(dir);
    Serial.print(' ');
    Serial.print(cellsDone);
    Serial.print(' ');
    Serial.print(msInCell);
    Serial.print(' ');
    Serial.println(stopDist, 1);
    return;
  }

  if (r == RUN_STOPPED) {
    // 이동 중 stop 받음
    // 형식: STOPPED <방향> <끝낸 칸 수> <이번 칸에서 움직인 ms>
    // 그 다음 stop 명령에 대한 답 DONE stop 0
    Serial.println();
    Serial.print("STOPPED ");
    Serial.print(dir);
    Serial.print(' ');
    Serial.print(cellsDone);
    Serial.print(' ');
    Serial.println(msInCell);
    Serial.println("DONE stop 0");
    return;
  }

  Serial.println();
  Serial.print("DONE ");
  Serial.print(dir);
  Serial.print(' ');
  Serial.println(steps);
}


// ===============================
// 지정 시간만큼 이동
// - 기다리는 동안 (1) 시리얼에 stop 이 왔는지, (2) 고른 센서 거리 를 계속 확인
// - sensor = -1 이면 거리 확인 안 함
// ===============================
RunResult runTimed(
    void (*action)(),
    unsigned long ms,
    int sensor,
    unsigned long &ranMs,
    float &stopDist
) {

  unsigned long start = millis();
  unsigned long lastCheck = 0;
  bool firstCheck = true;
  int hits = 0;

  for (int i = 0; i < 4; i++) syncAdj[i] = 0;
  syncActive = syncEnabled;
  unsigned long lastSync = 0;

  currentAction = action;
  action();

  while (millis() - start < ms) {

    // 1) 이동 중 stop 확인
    if (pollStopDuringMove()) {
      currentAction = nullptr;   // 급정지: 감속 없이 바로 브레이크
      stopMotor();
      ranMs = millis() - start;
      delay(100);
      return RUN_STOPPED;
    }

    // 1.5) 엔코더로 4바퀴 속도 맞추기
    unsigned long el = millis() - start;
    if (syncActive && el >= SYNC_START_MS && millis() - lastSync >= SYNC_MS) {
      lastSync = millis();

      unsigned long c[4];
      unsigned long sum = 0, mx = 0, mn = 0xFFFFFFFFUL;
      for (int i = 0; i < 4; i++) {
        c[i] = encCount[i];
        sum += c[i];
        if (c[i] > mx) mx = c[i];
        if (c[i] < mn) mn = c[i];
      }

      // 엔코더 하나가 안 들어오면(선 빠짐) 이번 이동은 보정 끔
      if (el >= 300 && mx > 40 && mn * 2 < mx) {
        syncActive = false;
        for (int i = 0; i < 4; i++) syncAdj[i] = 0;
        Serial.println();
        Serial.println("SYNC OFF (엔코더 하나가 안 들어옴 -> 이번 이동은 보정 없이)");
        currentAction();
      } else {
        float mean = sum / 4.0f;
        for (int i = 0; i < 4; i++) {
          int a = (int)(SYNC_KP * (mean - (float)c[i]));
          if (a >  SYNC_MAX_ADJ) a =  SYNC_MAX_ADJ;
          if (a < -SYNC_MAX_ADJ) a = -SYNC_MAX_ADJ;
          syncAdj[i] = a;
        }
        currentAction();   // 보정값 반영해서 PWM 다시 걸기
      }
    }

    // 2) 가는 방향 센서 확인
    if (sensor >= 0 && (firstCheck || millis() - lastCheck >= SENSOR_INTERVAL_MS)) {

      firstCheck = false;
      lastCheck = millis();

      float d = readDistanceCm(sensor, MOVE_TIMEOUT_US);

      if (PRINT_DISTANCE) {
        Serial.print("dist ");
        Serial.print(SONAR_NAME[sensor]);
        Serial.print(' ');
        Serial.println(d, 1);
      }

      // 기준 이하가 연속 CONFIRM_COUNT 번이면 정지
      if (d > 0 && d <= STOP_DISTANCE_CM) {
        hits++;
      } else {
        hits = 0;
      }

      if (hits >= CONFIRM_COUNT) {
        currentAction = nullptr;   // 급정지: 감속 없이 바로 브레이크
        stopMotor();
        ranMs = millis() - start;
        stopDist = d;
        delay(100);
        return RUN_OBSTACLE;
      }
    }
  }

  stopMotor();
  ranMs = ms;

  delay(100);   // 멈춘 뒤 관성 정리
  return RUN_DONE;
}


// ===============================
// 이동 중 시리얼 확인
// - "stop" 줄이 오면 true
// - 다른 명령이면 pendingLine 에 저장해 두고 이동 끝난 뒤 처리
// ===============================
bool pollStopDuringMove() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n') {
      String l = moveBuf;
      moveBuf = "";
      l.trim();

      String low = l;
      low.toLowerCase();

      if (low == "stop") {
        return true;
      }
      if (l.length() > 0) {
        pendingLine = l;
      }
    }
    else if (c != '\r') {
      moveBuf += c;
      if (moveBuf.length() > 64) {
        moveBuf = "";
      }
    }
  }
  return false;
}


// ===============================
// 기본 속도 x 바퀴별 보정 (0~255)
// ===============================
int trimmed(int base, float trim) {
  int v = (int)(base * trim * speedScale + 0.5f);
  if (v > 255) v = 255;
  if (v < 0) v = 0;
  return v;
}


// ===============================
// 개별 모터 제어
// inverted = false : forward -> PWM / LOW
// inverted = true  : forward -> LOW / PWM
// ===============================
int wheelIndexOf(int in1) {
  if (in1 == FL_IN1) return 0;
  if (in1 == FR_IN1) return 1;
  if (in1 == RL_IN1) return 2;
  if (in1 == RR_IN1) return 3;
  return -1;
}

void driveMotor(int in1, int in2, bool forward, bool inverted, int speed) {

  // 실시간 속도 맞추기 보정 더하기
  if (syncActive) {
    int w = wheelIndexOf(in1);
    if (w >= 0) {
      speed += (int)(syncAdj[w] * speedScale);
      if (speed > 255) speed = 255;
      if (speed < 0) speed = 0;
    }
  }

  motorsRunning = true;

  bool direction = forward;
  if (inverted) {
    direction = !direction;
  }

  if (direction) {
    analogWrite(in1, speed);
    digitalWrite(in2, LOW);
  } else {
    digitalWrite(in1, LOW);
    analogWrite(in2, speed);
  }
}


void stopMotorPair(int in1, int in2) {
  analogWrite(in1, 0);
  analogWrite(in2, 0);
  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
}


// 전체 정지: 달리던 중이면 4바퀴 동시에 짧게 브레이크 -> 전원 끊기
// (그냥 끊으면 바퀴마다 관성으로 서는 시점이 달라서 마지막에 틀어짐)
void stopMotor() {
  digitalWrite(LED_PIN, LOW);

  // 1) 4바퀴 같이 감속 (급정지면 건너뜀)
  bool ramped = false;
  if (motorsRunning && currentAction != nullptr) {
    ramped = true;
    for (int k = RAMP_STEPS - 1; k >= 1; k--) {
      speedScale = (float)k / RAMP_STEPS;
      currentAction();
      delay(RAMP_MS / RAMP_STEPS);
    }
    speedScale = 1.0;
  }
  currentAction = nullptr;

  // 2) 짧게 브레이크
  if (motorsRunning) {
    analogWrite(FL_IN1, 255); analogWrite(FL_IN2, 255);
    analogWrite(FR_IN1, 255); analogWrite(FR_IN2, 255);
    analogWrite(RL_IN1, 255); analogWrite(RL_IN2, 255);
    analogWrite(RR_IN1, 255); analogWrite(RR_IN2, 255);
    delay(ramped ? BRAKE_MS : EMERGENCY_BRAKE_MS);
  }

  stopMotorPair(FL_IN1, FL_IN2);
  stopMotorPair(FR_IN1, FR_IN2);
  stopMotorPair(RL_IN1, RL_IN2);
  stopMotorPair(RR_IN1, RR_IN2);

  motorsRunning = false;
  syncActive = false;
}


// ===============================
// 전진 / 후진
// ===============================
void moveForward() {
  digitalWrite(LED_PIN, HIGH);
  driveMotor(FL_IN1, FL_IN2, true, FL_INV, trimmed(MOTOR_SPEED, FL_TRIM));
  driveMotor(FR_IN1, FR_IN2, true, FR_INV, trimmed(MOTOR_SPEED, FR_TRIM));
  driveMotor(RL_IN1, RL_IN2, true, RL_INV, trimmed(MOTOR_SPEED, RL_TRIM));
  driveMotor(RR_IN1, RR_IN2, true, RR_INV, trimmed(MOTOR_SPEED, RR_TRIM));
}

void moveBackward() {
  digitalWrite(LED_PIN, HIGH);
  driveMotor(FL_IN1, FL_IN2, false, FL_INV, trimmed(MOTOR_SPEED, FL_TRIM));
  driveMotor(FR_IN1, FR_IN2, false, FR_INV, trimmed(MOTOR_SPEED, FR_TRIM));
  driveMotor(RL_IN1, RL_IN2, false, RL_INV, trimmed(MOTOR_SPEED, RL_TRIM));
  driveMotor(RR_IN1, RR_IN2, false, RR_INV, trimmed(MOTOR_SPEED, RR_TRIM));
}


// ===============================
// 왼쪽 횡이동: FL 후진, FR 전진, RL 전진, RR 후진
// ===============================
void strafeLeft() {
  digitalWrite(LED_PIN, HIGH);
  driveMotor(FL_IN1, FL_IN2, false, FL_INV, trimmed(STRAFE_SPEED, LFL_TRIM));
  driveMotor(FR_IN1, FR_IN2, true,  FR_INV, trimmed(STRAFE_SPEED, LFR_TRIM));
  driveMotor(RL_IN1, RL_IN2, true,  RL_INV, trimmed(STRAFE_SPEED, LRL_TRIM));
  driveMotor(RR_IN1, RR_IN2, false, RR_INV, trimmed(STRAFE_SPEED, LRR_TRIM));
}


// ===============================
// 오른쪽 횡이동: FL 전진, FR 후진, RL 후진, RR 전진
// ===============================
void strafeRight() {
  digitalWrite(LED_PIN, HIGH);
  driveMotor(FL_IN1, FL_IN2, true,  FL_INV, trimmed(STRAFE_SPEED, SFL_TRIM));
  driveMotor(FR_IN1, FR_IN2, false, FR_INV, trimmed(STRAFE_SPEED, SFR_TRIM));
  driveMotor(RL_IN1, RL_IN2, false, RL_INV, trimmed(STRAFE_SPEED, SRL_TRIM));
  driveMotor(RR_IN1, RR_IN2, true,  RR_INV, trimmed(STRAFE_SPEED, SRR_TRIM));
}


// ===============================
// 초음파 거리 (cm). 응답이 없으면 -1
// ===============================
float readDistanceCm(int sensor, unsigned long timeoutUs) {
  int trig = TRIG_PINS[sensor];
  int echo = ECHO_PINS[sensor];

  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);

  unsigned long duration = pulseIn(echo, HIGH, timeoutUs);

  if (duration == 0) {
    return -1;
  }
  return duration * 0.0343f / 2.0f;
}


// ===============================
// 4방향 거리 한 줄 출력
// 예: DIST front 52.3 left -1.0 back 120.4 right 33.1
// 센서끼리 초음파가 섞이지 않게 하나씩 30ms 간격으로 잼
// ===============================
void printAllDistances() {
  Serial.print("DIST");
  for (int i = 0; i < SONAR_COUNT; i++) {
    float d = readDistanceCm(i, DIST_TIMEOUT_US);
    Serial.print(' ');
    Serial.print(SONAR_NAME[i]);
    Serial.print(' ');
    Serial.print(d, 1);
    delay(30);
  }
  Serial.println();
}


// ===============================
// 엔코더 유틸
// ===============================
void encReset() {
  for (int i = 0; i < ENC_COUNT; i++) encCount[i] = 0;
}

// 바퀴별 펄스 + 가장 많이 돈 바퀴 대비 % + 추천 TRIM
void printEncoder(int mode) {
  bool strafe = (mode != 0);
  unsigned long c[ENC_COUNT];
  for (int i = 0; i < ENC_COUNT; i++) c[i] = encCount[i];

  const float fwdTrims[ENC_COUNT]    = {FL_TRIM, FR_TRIM, RL_TRIM, RR_TRIM};
  const float strafeTrims[ENC_COUNT] = {SFL_TRIM, SFR_TRIM, SRL_TRIM, SRR_TRIM};
  const float leftTrims[ENC_COUNT]   = {LFL_TRIM, LFR_TRIM, LRL_TRIM, LRR_TRIM};
  const float* trims = (mode == 1) ? strafeTrims : (mode == 2 ? leftTrims : fwdTrims);

  unsigned long mx = 0, mn = 0xFFFFFFFFUL;
  for (int i = 0; i < ENC_COUNT; i++) {
    if (c[i] > mx) mx = c[i];
    if (c[i] < mn) mn = c[i];
  }

  Serial.println();
  Serial.print("ENC");
  for (int i = 0; i < ENC_COUNT; i++) {
    Serial.print(' ');
    Serial.print(WHEEL_NAME[i]);
    Serial.print(' ');
    Serial.print(c[i]);
  }
  Serial.println();

  if (mx == 0 || mn == 0) {
    Serial.println("ENC WARN: 0 인 바퀴 있음 -> 그 바퀴 C1/VCC/GND 확인 (RR 이면 풀업 10k)");
    return;
  }

  Serial.print("ENC%");
  for (int i = 0; i < ENC_COUNT; i++) {
    Serial.print(' ');
    Serial.print(WHEEL_NAME[i]);
    Serial.print(' ');
    Serial.print(c[i] * 100UL / mx);
  }
  Serial.println();

  // 가장 느린 바퀴에 나머지를 맞춘 TRIM (이번 이동 기준)
  Serial.print(mode == 1 ? "SUGGEST(right)" : (mode == 2 ? "SUGGEST(left)" : "SUGGEST"));
  for (int i = 0; i < ENC_COUNT; i++) {
    Serial.print(' ');
    if (mode == 1) Serial.print('S');
    if (mode == 2) Serial.print('L');
    Serial.print(WHEEL_NAME[i]);
    Serial.print("_TRIM ");
    Serial.print(trims[i] * (float)mn / (float)c[i], 2);
  }
  Serial.println();
}