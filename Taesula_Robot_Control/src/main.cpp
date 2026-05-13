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

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  stopMotor();

  Serial.println("ESP32 Robot Control + Ultrasonic Test Start");
  Serial.println("Command List:");
  Serial.println("F = Forward");
  Serial.println("B = Backward");
  Serial.println("L = Left");
  Serial.println("R = Right");
  Serial.println("S = Stop");
  Serial.println("D = Distance Check");
}

void loop() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    handleCommand(command);
  }
}

void handleCommand(char command) {
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
  else {
    Serial.println("Unknown command");
  }
}

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

bool isObstacleDetected() {
  long distance = getDistanceCm();

  if (distance > 0 && distance <= OBSTACLE_DISTANCE) {
    return true;
  }

  return false;
}

void moveForward() {
  Serial.println("Robot Action: FORWARD");
  digitalWrite(LED_PIN, HIGH);
}

void moveBackward() {
  Serial.println("Robot Action: BACKWARD");
  digitalWrite(LED_PIN, HIGH);
}

void turnLeft() {
  Serial.println("Robot Action: LEFT");
  digitalWrite(LED_PIN, HIGH);
}

void turnRight() {
  Serial.println("Robot Action: RIGHT");
  digitalWrite(LED_PIN, HIGH);
}

void stopMotor() {
  Serial.println("Robot Action: STOP");
  digitalWrite(LED_PIN, LOW);
}