#include <Arduino.h>

// 테스트용 LED 핀
const int LED_PIN = 2;

// 초음파 센서 핀
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;

// ===============================
// L298N #1: 앞바퀴 모터드라이버
// OUT1/OUT2 -> 앞왼쪽 모터
// OUT3/OUT4 -> 앞오른쪽 모터
// ===============================
const int FL_IN1 = 26;  // Front Left IN1
const int FL_IN2 = 27;  // Front Left IN2

const int FR_IN1 = 14;  // Front Right IN3
const int FR_IN2 = 12;  // Front Right IN4

// ===============================
// L298N #2: 뒷바퀴 모터드라이버
// OUT1/OUT2 -> 뒤왼쪽 모터
// OUT3/OUT4 -> 뒤오른쪽 모터
// ===============================
const int RL_IN1 = 25;  // Rear Left IN1
const int RL_IN2 = 33;  // Rear Left IN2

const int RR_IN1 = 32;  // Rear Right IN3
const int RR_IN2 = 13;  // Rear Right IN4

// 장애물 판단 기준 거리(cm)
const int OBSTACLE_DISTANCE = 15;

// 자동 바닥 주행 테스트 모드
// true  = 전원 켜면 3초 뒤 자동 전진
// false = 시리얼 명령 입력해야 움직임
const bool AUTO_TEST_MODE = true;

// 자동 주행 시작 전 대기 시간(ms)
const unsigned long START_DELAY_MS = 3000;

const unsigned long FORWARD_RUN_MS = 3000;
// 초음파 센서 확인 간격(ms)
const unsigned long SENSOR_CHECK_INTERVAL_MS = 200;

// 자동 테스트 상태 변수
bool autoStarted = false;
bool autoFinished = false;
bool autoStoppedByObstacle = false;
unsigned long startTime = 0;
unsigned long forwardStartTime = 0;
unsigned long lastSensorCheckTime = 0;

// 함수 선언
void moveForward();
void moveBackward();
void turnLeft();
void turnRight();
void stopMotor();

void setMotor(int in1, int in2, bool forward);
void handleCommand(char command);
void runAutoTestMode();

long getDistanceCm();
bool isObstacleDetected();
bool isObstacleByDistance(long distance);
void testObstacleDetection(long testDistance);

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  // 앞바퀴 모터 핀 설정
  pinMode(FL_IN1, OUTPUT);
  pinMode(FL_IN2, OUTPUT);
  pinMode(FR_IN1, OUTPUT);
  pinMode(FR_IN2, OUTPUT);

  // 뒷바퀴 모터 핀 설정
  pinMode(RL_IN1, OUTPUT);
  pinMode(RL_IN2, OUTPUT);
  pinMode(RR_IN1, OUTPUT);
  pinMode(RR_IN2, OUTPUT);

  stopMotor();

  startTime = millis();

  Serial.println("ESP32 4-Wheel Robot Control Start");
  Serial.println("Command List:");
  Serial.println("F = Forward");
  Serial.println("B = Backward");
  Serial.println("L = Left");
  Serial.println("R = Right");
  Serial.println("S = Stop");
  Serial.println("D = Real distance check using ultrasonic sensor");
  Serial.println("T + number = Test obstacle detection with virtual distance");
  Serial.println("Example: T10, T30");

  if (AUTO_TEST_MODE) {
    Serial.println("AUTO TEST MODE = ON");
    Serial.println("Robot will move forward after 3 seconds.");
    Serial.println("Robot will stop automatically after 3 seconds of movement.");
    Serial.println("Obstacle detected -> STOP");
  } else {
    Serial.println("AUTO TEST MODE = OFF");
    Serial.println("Use serial commands to control robot.");
  }
}

void loop() {
  if (AUTO_TEST_MODE) {
    runAutoTestMode();
  }

  // 자동 모드여도 시리얼 명령은 디버깅용으로 받을 수 있게 유지
  if (Serial.available() > 0) {
    char command = Serial.read();
    handleCommand(command);
  }
}

// 자동 주행 테스트 함수
// 자동 주행 테스트 함수
// 전원 켜진 뒤 3초 대기 → 3초 전진 → 4바퀴 전체 정지
void runAutoTestMode() {
  // 자동 테스트가 끝났거나 장애물로 정지한 경우 계속 정지 유지
  if (autoFinished || autoStoppedByObstacle) {
    stopMotor();
    return;
  }

  // 전원 켜자마자 튀어나가지 않도록 3초 대기
  if (!autoStarted) {
    if (millis() - startTime < START_DELAY_MS) {
      stopMotor();
      return;
    }

    Serial.println("AUTO TEST START: FORWARD");
    moveForward();

    autoStarted = true;
    forwardStartTime = millis();
    lastSensorCheckTime = millis();
  }

  // 3초 동안 전진 후 자동 정지
  if (millis() - forwardStartTime >= FORWARD_RUN_MS) {
    Serial.println("AUTO TEST FINISHED: STOP");
    stopMotor();

    autoFinished = true;
    return;
  }

  // 전진 중 일정 간격마다 초음파 센서 확인
  /*if (millis() - lastSensorCheckTime >= SENSOR_CHECK_INTERVAL_MS) {
    lastSensorCheckTime = millis();

    if (isObstacleDetected()) {
      Serial.println("Obstacle detected during auto test!");
      Serial.println("Robot Action: STOP");
      stopMotor();

      autoStoppedByObstacle = true;
      return;
    }
  }*/
}

// 모터 하나 방향 제어 함수
void setMotor(int in1, int in2, bool forward) {
  if (forward) {
    digitalWrite(in1, HIGH);
    digitalWrite(in2, LOW);
  } else {
    digitalWrite(in1, LOW);
    digitalWrite(in2, HIGH);
  }
}

// 전진
void moveForward() {
  Serial.println("Robot Action: FORWARD");
  digitalWrite(LED_PIN, HIGH);

  setMotor(FL_IN1, FL_IN2, true);
  setMotor(FR_IN1, FR_IN2, true);
  setMotor(RL_IN1, RL_IN2, true);
  setMotor(RR_IN1, RR_IN2, true);
}

// 후진
void moveBackward() {
  Serial.println("Robot Action: BACKWARD");
  digitalWrite(LED_PIN, HIGH);

  setMotor(FL_IN1, FL_IN2, false);
  setMotor(FR_IN1, FR_IN2, false);
  setMotor(RL_IN1, RL_IN2, false);
  setMotor(RR_IN1, RR_IN2, false);
}

// 좌회전
// 왼쪽 바퀴 후진, 오른쪽 바퀴 전진
void turnLeft() {
  Serial.println("Robot Action: LEFT");
  digitalWrite(LED_PIN, HIGH);

  setMotor(FL_IN1, FL_IN2, false);
  setMotor(RL_IN1, RL_IN2, false);

  setMotor(FR_IN1, FR_IN2, true);
  setMotor(RR_IN1, RR_IN2, true);
}

// 우회전
// 왼쪽 바퀴 전진, 오른쪽 바퀴 후진
void turnRight() {
  Serial.println("Robot Action: RIGHT");
  digitalWrite(LED_PIN, HIGH);

  setMotor(FL_IN1, FL_IN2, true);
  setMotor(RL_IN1, RL_IN2, true);

  setMotor(FR_IN1, FR_IN2, false);
  setMotor(RR_IN1, RR_IN2, false);
}

// 정지
void stopMotor() {
  digitalWrite(LED_PIN, LOW);

  digitalWrite(FL_IN1, LOW);
  digitalWrite(FL_IN2, LOW);

  digitalWrite(FR_IN1, LOW);
  digitalWrite(FR_IN2, LOW);

  digitalWrite(RL_IN1, LOW);
  digitalWrite(RL_IN2, LOW);

  digitalWrite(RR_IN1, LOW);
  digitalWrite(RR_IN2, LOW);
}

// 명령 처리 함수
void handleCommand(char command) {
  if (command == '\n' || command == '\r' || command == ' ') {
    return;
  }

  if (command == 'F' || command == 'f') {
    if (isObstacleDetected()) {
      Serial.println("Obstacle detected! Robot stopped.");
      autoStoppedByObstacle = true;
      stopMotor();
    } else {
      autoStoppedByObstacle = false;
      moveForward();
    }
  }
  else if (command == 'B' || command == 'b') {
    autoStoppedByObstacle = false;
    moveBackward();
  }
  else if (command == 'L' || command == 'l') {
    autoStoppedByObstacle = false;
    turnLeft();
  }
  else if (command == 'R' || command == 'r') {
    autoStoppedByObstacle = false;
    turnRight();
  }
  else if (command == 'S' || command == 's') {
    autoStoppedByObstacle = true;
    stopMotor();
    Serial.println("Robot Action: STOP");
  }
  else if (command == 'D' || command == 'd') {
    getDistanceCm();
  }
  else if (command == 'T' || command == 't') {
    delay(50);

    long testDistance = Serial.parseInt();

    if (testDistance > 0) {
      testObstacleDetection(testDistance);
    } else {
      Serial.println("Invalid test distance. Example: T10 or T30");
    }
  }
  else {
    Serial.println("Unknown command");
  }
}

// 실제 초음파 센서 거리 측정 함수
long getDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0) {
    Serial.println("Distance: No echo");
    return -1;
  }

  long distance = duration * 0.034 / 2;

  Serial.print("Distance: ");
  Serial.print(distance);
  Serial.println(" cm");

  return distance;
}

// 실제 센서값으로 장애물 감지
bool isObstacleDetected() {
  long distance = getDistanceCm();
  return isObstacleByDistance(distance);
}

// 거리값 기준 장애물 판단
bool isObstacleByDistance(long distance) {
  return distance > 0 && distance <= OBSTACLE_DISTANCE;
}

// 가상 거리값 테스트 함수
void testObstacleDetection(long testDistance) {
  Serial.print("Test Distance: ");
  Serial.print(testDistance);
  Serial.println(" cm");

  if (isObstacleByDistance(testDistance)) {
    Serial.println("Obstacle detected in test data!");
    stopMotor();
  } else {
    Serial.println("No obstacle in test data.");
  }
}