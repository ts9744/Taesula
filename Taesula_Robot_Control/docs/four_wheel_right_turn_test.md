\# Four Wheel Right Turn Test Result



\## Test Objective



The purpose of this test is to verify that the robot can move forward briefly, perform a right turn, and then stop all wheels using the ESP32 auto test mode.



\## Test Conditions



\- ESP32 power source: USB power bank or USB power

\- Motor power source: separate battery pack

\- ESP32 GND and motor driver GND connected as common ground

\- Auto test type: RIGHT

\- Front-left motor control pin changed from GPIO26 to GPIO16 due to the GPIO26 signal issue



\## Test Procedure



1\. Upload the right turn auto test code to the ESP32.

2\. Power on the ESP32 and wait for 3 seconds.

3\. Check that all four wheels move forward for 1 second.

4\. Check that the right-side wheels stop and the left-side wheels rotate for 1 second.

5\. Check that all wheels stop after the test sequence.



\## Test Result



The ESP32 auto test mode successfully executed the sequence of moving forward for 1 second, performing a right turn, and stopping all wheels at the end of the test.



\## Note



GPIO26 was avoided because the front-left wheel rotated unexpectedly during the stop-only motor test. The front-left motor control pin was changed to GPIO16 before the right turn test.

