#include <Arduino.h>

// 테스트용 LED 핀
const int LED_PIN = 2;

// 초음파 센서 핀
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;

// ===============================
// L298N #1: 앞바퀴 모터 드라이버
// OUT1/OUT2 -> 앞왼쪽 모터
// OUT3/OUT4 -> 앞오른쪽 모터
// ===============================
const int FL_IN1 = 16;  // Front Left IN1
const int FL_IN2 = 27;  // Front Left IN2
const int FR_IN1 = 14;  // Front Right IN3
const int FR_IN2 = 12;  // Front Right IN4

// ===============================
// L298N #2: 뒷바퀴 모터 드라이버
// OUT1/OUT2 -> 뒤왼쪽 모터
// OUT3/OUT4 -> 뒤오른쪽 모터
// ===============================
const int RL_IN1 = 32;  // Rear Left IN1
const int RL_IN2 = 13;  // Rear Left IN2
const int RR_IN1 = 25;  // Rear Right IN3
const int RR_IN2 = 33;  // Rear Right IN4

// 1칸 이동 시간(ms) - 바닥 테스트 후 조정
const unsigned long FORWARD_RUN_MS = 1000;
const unsigned long STRAFE_RUN_MS = 1000;

// 속도(PWM 0~255)
const int MOTOR_SPEED = 150;
const int STRAFE_SPEED = 200;

// 시리얼 한 줄 버퍼
String lineBuf;

// 함수 선언
void setMotor(int in1, int in2, bool forward, int speed);
void stopMotorPair(int in1, int in2);
void stopMotor();
void moveForward();
void moveBackward();
void strafeLeft();
void strafeRight();
void runTimed(void (*action)(), unsigned long ms);
void handleLine(String line);
long getDistanceCm();


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
      if (lineBuf.length() > 64) {  // 쓰레기 입력 방지
        lineBuf = "";
      }
    }
  }
}

// ===============================
// 시리얼 명령 처리
// 입력: "forward 3", "backward 1", "left 2", "right 1", "stop", "dist"
// 응답: "DONE <방향> <칸수>" / "DIST <cm>" / "ERR <내용>"
// ===============================
void handleLine(String line) {
  int sp = line.indexOf(' ');
  String dir = (sp == -1) ? line : line.substring(0, sp);
  int steps = (sp == -1) ? 1 : line.substring(sp + 1).toInt();
  dir.toLowerCase();

  if (dir == "stop") {
    stopMotor();
    Serial.println("DONE stop 0");
    return;
  }

  if (dir == "dist") {
    Serial.print("DIST ");
    Serial.println(getDistanceCm());
    return;
  }

  if (steps < 1) steps = 1;

  void (*action)() = nullptr;
  unsigned long runMs = 0;

  if (dir == "forward")       { action = moveForward;  runMs = FORWARD_RUN_MS; }
  else if (dir == "backward") { action = moveBackward; runMs = FORWARD_RUN_MS; }
  else if (dir == "left")     { action = strafeLeft;   runMs = STRAFE_RUN_MS; }
  else if (dir == "right")    { action = strafeRight;  runMs = STRAFE_RUN_MS; }
  else {
    Serial.println("ERR unknown " + line);
    return;
  }

  for (int i = 0; i < steps; i++) {
    runTimed(action, runMs);
  }

  Serial.print("DONE ");
  Serial.print(dir);
  Serial.print(' ');
  Serial.println(steps);
}

// 동작을 ms 동안 실행 후 정지
void runTimed(void (*action)(), unsigned long ms) {
  action();
  delay(ms);
  stopMotor();
  delay(100);  // 칸 사이 관성 정리
}

// ===============================
// 모터 제어
// ===============================
void setMotor(int in1, int in2, bool forward, int speed) {
  if (forward) {
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

void stopMotor() {
  digitalWrite(LED_PIN, LOW);
  stopMotorPair(FL_IN1, FL_IN2);
  stopMotorPair(FR_IN1, FR_IN2);
  stopMotorPair(RL_IN1, RL_IN2);
  stopMotorPair(RR_IN1, RR_IN2);
}

// 전진: 4바퀴 전진
void moveForward() {
  digitalWrite(LED_PIN, HIGH);
  setMotor(FL_IN1, FL_IN2, true, MOTOR_SPEED);
  setMotor(FR_IN1, FR_IN2, true, MOTOR_SPEED);
  setMotor(RL_IN1, RL_IN2, true, MOTOR_SPEED);
  setMotor(RR_IN1, RR_IN2, true, MOTOR_SPEED);
}

// 후진: 4바퀴 후진
void moveBackward() {
  digitalWrite(LED_PIN, HIGH);
  setMotor(FL_IN1, FL_IN2, false, MOTOR_SPEED);
  setMotor(FR_IN1, FR_IN2, false, MOTOR_SPEED);
  setMotor(RL_IN1, RL_IN2, false, MOTOR_SPEED);
  setMotor(RR_IN1, RR_IN2, false, MOTOR_SPEED);
}

// 메카넘 왼쪽 횡이동: FL 후진, FR 전진, RL 전진, RR 후진
void strafeLeft() {
  digitalWrite(LED_PIN, HIGH);
  setMotor(FL_IN1, FL_IN2, false, STRAFE_SPEED);
  setMotor(FR_IN1, FR_IN2, true,  STRAFE_SPEED);
  setMotor(RL_IN1, RL_IN2, true,  STRAFE_SPEED);
  setMotor(RR_IN1, RR_IN2, false, STRAFE_SPEED);
}

// 메카넘 오른쪽 횡이동: FL 전진, FR 후진, RL 후진, RR 전진
void strafeRight() {
  digitalWrite(LED_PIN, HIGH);
  setMotor(FL_IN1, FL_IN2, true,  STRAFE_SPEED);
  setMotor(FR_IN1, FR_IN2, false, STRAFE_SPEED);
  setMotor(RL_IN1, RL_IN2, false, STRAFE_SPEED);
  setMotor(RR_IN1, RR_IN2, true,  STRAFE_SPEED);
}

// ===============================
// 초음파 센서 (현재 이동 판단에는 미사용, "dist" 명령으로 확인용)
// ===============================
long getDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) {
    return -1;
  }
  return duration * 0.034 / 2;
}