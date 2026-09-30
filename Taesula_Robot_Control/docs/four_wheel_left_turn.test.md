# Four Wheel Left Turn Test Result

## Test Objective

The purpose of this test is to verify that the robot can move forward briefly, perform a left turn, and then stop all four wheels using the ESP32 auto test mode.

## Test Conditions

- ESP32 power source: USB power bank or USB power
- Motor power source: separate battery pack
- ESP32 GND and motor driver GND connected as common ground
- Ultrasonic sensor not connected during this motor-only test
- Auto test type: LEFT

## Test Procedure

1. Upload the left turn auto test code to the ESP32.
2. Power on the ESP32 and wait for 3 seconds.
3. Check that all four wheels move forward for 1 second.
4. Check that the robot performs a left turn.
5. Check that all four wheels stop after the test sequence.

## Issue Found During Test

During the left turn test, the robot moved forward for 1 second and then performed a left turn.  
With the current turn duration set to about 1 second, the robot turned approximately 60 degrees.

## Future Adjustment Plan

For the midterm demonstration and final presentation, the left turn angle needs to be closer to 90 degrees.  
To improve the turn angle, the left turn duration will be increased from 1 second to about 1.5 seconds and tested again.

## Test Result

The ESP32 auto test mode successfully executed the sequence of moving forward for 1 second, performing a left turn, and stopping all wheels at the end of the test.