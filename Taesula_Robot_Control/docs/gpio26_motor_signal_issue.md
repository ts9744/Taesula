\# GPIO26 Motor Signal Issue



\## Purpose



This document records the debugging result for the unexpected front-left wheel rotation issue during the ESP32 motor control test.



\## Problem



During the right turn test, the front-left wheel started rotating immediately when ESP32 power was connected, even before the auto test sequence started.



\## Test Setup



\- Stop-only motor test code was uploaded to the ESP32.

\- All motor control pins were set to LOW in the code.

\- Front motor driver IN2, IN3, and IN4 were connected to GND.

\- Front motor driver IN1 was connected to ESP32 GPIO26.

\- ESP32 GND and motor driver GND were connected as common ground.



\## Test Result



Even though GPIO26 was set to LOW in the stop-only test code, the front-left wheel rotated when IN1 was connected to GPIO26.



\## Expected Behavior



The front-left wheel should remain stopped because IN1 was expected to be LOW and IN2 was connected to GND.



\## Analysis



The test result suggests that GPIO26 is not behaving as expected in the current wiring setup.  

Possible causes include a breadboard contact issue, incorrect pin position, jumper wire issue, or GPIO26 signal instability in the current hardware configuration.



\## Temporary Decision



GPIO26 will be avoided for the front-left motor control pin until the wiring environment is improved.



\## Next Step



\- Secure a larger breadboard or female-to-female jumper wires.

\- Move the front-left motor control signal from GPIO26 to another output-capable GPIO pin.

\- Retest the stop-only motor state.

\- Continue the right turn test after resolving the GPIO26 issue.

