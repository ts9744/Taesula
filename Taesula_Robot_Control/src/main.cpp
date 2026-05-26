#include <Arduino.h>

// 테스트용 LED 핀
const int LED_PIN = 2;

// 초음파 센서 핀
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;

// 한쪽 모터드라이버 제어 핀
// L298N 기준: OUT1/OUT2에 연결된 모터를 IN1/IN2로 제어
const int MOTOR_IN1 = 26;
const int MOTOR_IN2 = 27;

// 장애물 판단 기준 거리(cm)
const int OBSTACLE_DISTANCE = 15;

// 자동 바닥 주행 테스트 모드
// true  = 노트북 시리얼 입력 없이 전원 켜면 자동 전진
// false = 기존처럼 시리얼 명령 F/B/L/R/S 입력으로 제어
const bool AUTO_TEST_MODE = true;

// 자동 주행 시작 전 대기 시간(ms)
const unsigned long START_DELAY_MS = 3000;

// 초음파 센서 측정 간격(ms)
const unsigned long SENSOR_CHECK_INTERVAL_MS = 200;

// 자동 테스트 상태 변수
bool autoStarted = false;
bool autoStoppedByObstacle = false;
unsigned long startTime = 0;
unsigned long lastSensorCheckTime = 0;

// 함수 선언
void moveForward();
void moveBackward();
void turnLeft();
void turnRight();
void stopMotor();

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

  // 모터 제어 핀 설정
  pinMode(MOTOR_IN1, OUTPUT);
  pinMode(MOTOR_IN2, OUTPUT);

  stopMotor();

  startTime = millis();

  Serial.println("ESP32 Robot Control + Standalone Auto Test Start");
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
    Serial.println("Obstacle detected -> STOP");
  } else {
    Serial.println("AUTO TEST MODE = OFF");
    Serial.println("Use serial commands to control robot.");
  }
}

void loop() {
  // 노트북 없이 바닥 주행 테스트
  if (AUTO_TEST_MODE) {
    runAutoTestMode();
  }

  // 기존 시리얼 명령도 디버깅용으로 유지
  if (Serial.available() > 0) {
    char command = Serial.read();
    handleCommand(command);
  }
}

// 자동 주행 테스트 함수
void runAutoTestMode() {
  // 장애물 감지 후에는 계속 정지 유지
  if (autoStoppedByObstacle) {
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
    lastSensorCheckTime = millis();
  }

  // 일정 간격마다 초음파 센서 확인
  if (millis() - lastSensorCheckTime >= SENSOR_CHECK_INTERVAL_MS) {
    lastSensorCheckTime = millis();

    if (isObstacleDetected()) {
      Serial.println("Obstacle detected during auto test!");
      Serial.println("Robot Action: STOP");
      stopMotor();
      autoStoppedByObstacle = true;
      return;
    }

    // 장애물이 없으면 계속 전진
    moveForward();
  }
}

// 명령 처리 함수
void handleCommand(char command) {
  // 엔터, 줄바꿈, 공백 문자는 명령으로 처리하지 않음
  if (command == '\n' || command == '\r' || command == ' ') {
    return;
  }

  if (command == 'F' || command == 'f') {
    if (isObstacleDetected()) {
      Serial.println("Obstacle detected! Robot stopped.");
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

// 전진
void moveForward() {
  Serial.println("Robot Action: FORWARD");
  digitalWrite(LED_PIN, HIGH);

  digitalWrite(MOTOR_IN1, HIGH);
  digitalWrite(MOTOR_IN2, LOW);
}

// 후진
void moveBackward() {
  Serial.println("Robot Action: BACKWARD");
  digitalWrite(LED_PIN, HIGH);

  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, HIGH);
}

// 좌회전
// 한쪽 모터만 연결한 테스트 단계에서는 전진과 동일하게 처리
void turnLeft() {
  Serial.println("Robot Action: LEFT");
  digitalWrite(LED_PIN, HIGH);

  digitalWrite(MOTOR_IN1, HIGH);
  digitalWrite(MOTOR_IN2, LOW);
}

// 우회전
// 한쪽 모터만 연결한 테스트 단계에서는 후진과 동일하게 처리
void turnRight() {
  Serial.println("Robot Action: RIGHT");
  digitalWrite(LED_PIN, HIGH);

  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, HIGH);
}

// 정지
void stopMotor() {
  Serial.println("Robot Action: STOP");
  digitalWrite(LED_PIN, LOW);

  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, LOW);
}