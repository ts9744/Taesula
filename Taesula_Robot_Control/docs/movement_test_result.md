# Four-Wheel Movement Test Result

## Test Purpose

The purpose of this test was to verify that the robot can move using the ESP32, two L298N motor drivers, and four motors.

This test was performed after confirming the basic ultrasonic sensor test and single motor driver control.

## Test Environment

- Controller: ESP32
- Motor Driver: L298N x 2
- Motors: 4 DC motors
- Sensor: Ultrasonic sensor
- Motor Power: External battery
- ESP32 Power: USB or power bank

## Test Procedure

1. Connected two motors to the front L298N motor driver.
2. Connected two motors to the rear L298N motor driver.
3. Connected the ESP32 GPIO pins to the IN1, IN2, IN3, and IN4 pins of both L298N modules.
4. Connected the GND of the ESP32 and both L298N modules together.
5. Uploaded the four-motor standalone test code to the ESP32.
6. Powered the ESP32 and motor drivers separately.
7. Checked whether all four wheels rotated in the forward direction.

## Test Result

All four wheels rotated successfully.

During the first test, one front wheel rotated in the opposite direction.  
The issue was resolved by swapping the M+ and M- motor lines of that wheel.

After correcting the motor direction, all four wheels rotated in the same forward direction.

## Issue

One motor showed weaker rotation compared to the others.  
For the current implementation, the robot will continue with the available motor configuration.

The motor issue will be handled in the next development stage by replacing the motor with a matching model or applying PWM-based speed compensation.

## Conclusion

The test confirmed that the ESP32 can control four motors through two L298N motor drivers.

The robot is now ready for further testing with standalone movement mode and ultrasonic obstacle detection.