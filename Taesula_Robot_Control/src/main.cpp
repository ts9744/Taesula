#include <Arduino.h>

// 테스트용 LED 핀
const int LED_PIN = 2;

// 초음파 센서 핀
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;

// 장애물 판단 기준 거리(cm)
const int OBSTACLE_DISTANCE = 15;

// 함수 선언
void moveForward();
void moveBackward();
void turnLeft();
void turnRight();
void stopMotor();

void handleCommand(char command);
long getDistanceCm();
bool isObstacleDetected();
bool isObstacleByDistance(long distance);
void testObstacleDetection(long testDistance);

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  stopMotor();

  Serial.println("ESP32 Robot Control + Sensor Data Test Start");
  Serial.println("Command List:");
  Serial.println("F = Forward");
  Serial.println("B = Backward");
  Serial.println("L = Left");
  Serial.println("R = Right");
  Serial.println("S = Stop");
  Serial.println("D = Real distance check using ultrasonic sensor");
  Serial.println("T + number = Test obstacle detection with virtual distance");
  Serial.println("Example: T10, T30");
}

void loop() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    handleCommand(command);
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
      moveForward();
    }
  }
  else if (command == 'B' || command == 'b') {
    moveBackward();
  }
  else if (command == 'L' || command == 'l') {
    turnLeft();
  }
  else if (command == 'R' || command == 'r') {
    turnRight();
  }
  else if (command == 'S' || command == 's') {
    stopMotor();
  }
  else if (command == 'D' || command == 'd') {
    getDistanceCm();
  }
  else if (command == 'T' || command == 't') {
    delay(50);  // 숫자가 들어올 시간을 잠깐 기다림

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
  if (distance > 0 && distance <= OBSTACLE_DISTANCE) {
    return true;
  }

  return false;
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
}

// 후진
void moveBackward() {
  Serial.println("Robot Action: BACKWARD");
  digitalWrite(LED_PIN, HIGH);
}

// 좌회전
void turnLeft() {
  Serial.println("Robot Action: LEFT");
  digitalWrite(LED_PIN, HIGH);
}

// 우회전
void turnRight() {
  Serial.println("Robot Action: RIGHT");
  digitalWrite(LED_PIN, HIGH);
}

// 정지
void stopMotor() {
  Serial.println("Robot Action: STOP");
  digitalWrite(LED_PIN, LOW);
}