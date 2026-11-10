#include <Arduino.h>

// 테스트용 LED
const int LED_PIN = 2;

// 초음파 센서 - 현재 1개 테스트용
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;

// ===============================
// ZK-BM1 #1 : 앞바퀴
// ===============================
const int FL_IN1 = 25;
const int FL_IN2 = 26;

const int FR_IN1 = 32;
const int FR_IN2 = 33;

// ===============================
// ZK-BM1 #2 : 뒷바퀴
// ===============================
const int RL_IN1 = 16;
const int RL_IN2 = 17;

const int RR_IN1 = 22;
const int RR_IN2 = 23;

// ===============================
// 이동 설정
// ===============================

// 1칸 이동 시간
const unsigned long FORWARD_RUN_MS = 1000;
const unsigned long STRAFE_RUN_MS  = 1000;

// 칸 출발 전 장애물 점검 (칸 34cm 기준: 다음 칸 장애물 6.5~34cm / 지도 벽 40.5cm -> 37cm)
const long BLOCK_DISTANCE_CM = 37;
const int PRECHECK_SAMPLES = 3;

// PWM 속도
const int MOTOR_SPEED  = 150;
const int STRAFE_SPEED = 200;

String lineBuf;


// ===============================
// 함수 선언
// ===============================
void driveMotor(int in1, int in2, bool forward, bool inverted, int speed);
void stopMotorPair(int in1, int in2);
void stopMotor();

void moveForward();
void moveBackward();
void strafeLeft();
void strafeRight();

void runTimed(void (*action)(), unsigned long ms);
void handleLine(String line);

long getDistanceCm();
long precheckDistanceCm();


// ===============================
// SETUP
// ===============================
void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

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

  Serial.println("READY");
}


// ===============================
// LOOP
// ===============================
void loop() {
  while (Serial.available() > 0) {

    char c = Serial.read();

    if (c == '\n') {

      lineBuf.trim();

      if (lineBuf.length() > 0) {
        handleLine(lineBuf);
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
// 예:
// FORWARD 3
// BACKWARD 1
// LEFT 2
// RIGHT 1
// STOP
// DIST
// ===============================
void handleLine(String line) {

  int sp = line.indexOf(' ');

  String dir =
      (sp == -1)
      ? line
      : line.substring(0, sp);

  int steps =
      (sp == -1)
      ? 1
      : line.substring(sp + 1).toInt();

  // FORWARD / forward 둘 다 처리
  dir.toLowerCase();


  // -------------------------------
  // 정지
  // -------------------------------
  if (dir == "stop") {

    stopMotor();

    Serial.println("DONE stop 0");

    return;
  }


  // -------------------------------
  // 초음파 거리
  // -------------------------------
  if (dir == "dist") {

    Serial.print("DIST ");
    Serial.println(getDistanceCm());

    return;
  }


  if (steps < 1) {
    steps = 1;
  }


  void (*action)() = nullptr;
  unsigned long runMs = 0;


  if (dir == "forward") {

    action = moveForward;
    runMs = FORWARD_RUN_MS;
  }

  else if (dir == "backward") {

    action = moveBackward;
    runMs = FORWARD_RUN_MS;
  }

  else if (dir == "left") {

    action = strafeLeft;
    runMs = STRAFE_RUN_MS;
  }

  else if (dir == "right") {

    action = strafeRight;
    runMs = STRAFE_RUN_MS;
  }

  else {

    Serial.println("ERR unknown " + line);

    return;
  }


  // -------------------------------
  // steps 만큼 반복
  // -------------------------------
  for (int i = 0; i < steps; i++) {
    // 칸 출발 전 점검: 앞쪽에 장애물이 있으면 출발하지 않고 보고한다
    if (dir == "forward") {
      long pd = precheckDistanceCm();
      if (pd > 0 && pd <= BLOCK_DISTANCE_CM) {
        Serial.println();
        Serial.print("OBSTACLE ");
        Serial.print(dir);
        Serial.print(' ');
        Serial.print(i);
        Serial.print(" 0 ");
        Serial.println(pd);
        return;
      }
    }
    runTimed(action, runMs);
  }


  Serial.print("DONE ");
  Serial.print(dir);
  Serial.print(' ');
  Serial.println(steps);
}


// ===============================
// 지정 시간만큼 동작 후 정지
// ===============================
void runTimed(
    void (*action)(),
    unsigned long ms
) {

  action();

  delay(ms);

  stopMotor();

  // 칸 사이 짧게 정지
  delay(100);
}


// ===============================
// 개별 모터 제어
//
// inverted = false
//   forward -> HIGH / LOW
//
// inverted = true
//   forward -> LOW / HIGH
// ===============================
void driveMotor(
    int in1,
    int in2,
    bool forward,
    bool inverted,
    int speed
) {

  // 실제 전기 방향 결정
  bool direction = forward;

  if (inverted) {
    direction = !direction;
  }


  if (direction) {

    analogWrite(in1, speed);
    digitalWrite(in2, LOW);
  }

  else {

    digitalWrite(in1, LOW);
    analogWrite(in2, speed);
  }
}


// ===============================
// 모터 한 개 정지
// ===============================
void stopMotorPair(
    int in1,
    int in2
) {

  analogWrite(in1, 0);
  analogWrite(in2, 0);

  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
}


// ===============================
// 전체 정지
// ===============================
void stopMotor() {

  digitalWrite(LED_PIN, LOW);

  stopMotorPair(FL_IN1, FL_IN2);
  stopMotorPair(FR_IN1, FR_IN2);
  stopMotorPair(RL_IN1, RL_IN2);
  stopMotorPair(RR_IN1, RR_IN2);
}


// ============================================================
// 실제 테스트 결과
//
// FL 전진 = LOW  / HIGH -> inverted = true
// FR 전진 = LOW  / HIGH -> inverted = true
// RL 전진 = HIGH / LOW  -> inverted = false
// RR 전진 = HIGH / LOW  -> inverted = false
// ============================================================


// ===============================
// 전진
// ===============================
void moveForward() {

  digitalWrite(LED_PIN, HIGH);

  driveMotor(
      FL_IN1, FL_IN2,
      true,
      true,
      MOTOR_SPEED
  );

  driveMotor(
      FR_IN1, FR_IN2,
      true,
      true,
      MOTOR_SPEED
  );

  driveMotor(
      RL_IN1, RL_IN2,
      true,
      false,
      MOTOR_SPEED
  );

  driveMotor(
      RR_IN1, RR_IN2,
      true,
      false,
      MOTOR_SPEED
  );
}


// ===============================
// 후진
// ===============================
void moveBackward() {

  digitalWrite(LED_PIN, HIGH);

  driveMotor(
      FL_IN1, FL_IN2,
      false,
      true,
      MOTOR_SPEED
  );

  driveMotor(
      FR_IN1, FR_IN2,
      false,
      true,
      MOTOR_SPEED
  );

  driveMotor(
      RL_IN1, RL_IN2,
      false,
      false,
      MOTOR_SPEED
  );

  driveMotor(
      RR_IN1, RR_IN2,
      false,
      false,
      MOTOR_SPEED
  );
}


// ===============================
// 왼쪽 횡이동
//
// 물리적 바퀴 방향:
// FL = 후진
// FR = 전진
// RL = 전진
// RR = 후진
// ===============================
void strafeLeft() {

  digitalWrite(LED_PIN, HIGH);

  driveMotor(
      FL_IN1, FL_IN2,
      false,
      true,
      STRAFE_SPEED
  );

  driveMotor(
      FR_IN1, FR_IN2,
      true,
      true,
      STRAFE_SPEED
  );

  driveMotor(
      RL_IN1, RL_IN2,
      true,
      false,
      STRAFE_SPEED
  );

  driveMotor(
      RR_IN1, RR_IN2,
      false,
      false,
      STRAFE_SPEED
  );
}


// ===============================
// 오른쪽 횡이동
//
// 물리적 바퀴 방향:
// FL = 전진
// FR = 후진
// RL = 후진
// RR = 전진
// ===============================
void strafeRight() {

  digitalWrite(LED_PIN, HIGH);

  driveMotor(
      FL_IN1, FL_IN2,
      true,
      true,
      STRAFE_SPEED
  );

  driveMotor(
      FR_IN1, FR_IN2,
      false,
      true,
      STRAFE_SPEED
  );

  driveMotor(
      RL_IN1, RL_IN2,
      false,
      false,
      STRAFE_SPEED
  );

  driveMotor(
      RR_IN1, RR_IN2,
      true,
      false,
      STRAFE_SPEED
  );
}


// ===============================
// 초음파 센서
// 현재 1개 테스트용
// ===============================
long getDistanceCm() {

  digitalWrite(TRIG_PIN, LOW);

  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);

  delayMicroseconds(10);

  digitalWrite(TRIG_PIN, LOW);


  long duration =
      pulseIn(
          ECHO_PIN,
          HIGH,
          30000
      );


  if (duration == 0) {
    return -1;
  }


  return duration * 0.034 / 2;
}

// ===============================
// 칸 출발 전 점검용 거리
// 3번 재서 유효한 값 중 가운데 값을 돌려준다. 하나도 못 쟀으면 -1.
// ===============================
long precheckDistanceCm() {
  long v[PRECHECK_SAMPLES];
  int n = 0;

  for (int k = 0; k < PRECHECK_SAMPLES; k++) {
    long d = getDistanceCm();
    if (d > 0) {
      v[n++] = d;
    }
    delay(30);
  }

  if (n == 0) {
    return -1;
  }

  // 작은 순서로 정렬
  for (int a = 0; a < n - 1; a++) {
    for (int b = a + 1; b < n; b++) {
      if (v[b] < v[a]) {
        long t = v[a];
        v[a] = v[b];
        v[b] = t;
      }
    }
  }

  return v[n / 2];
}