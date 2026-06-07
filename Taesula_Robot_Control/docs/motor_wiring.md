# Motor Driver Wiring

## Overview

This document describes the wiring used for the ESP32 robot motor control test.

The robot uses two L298N motor drivers to control four DC motors.

- L298N #1 controls the front two motors.
- L298N #2 controls the rear two motors.
- ESP32 sends HIGH/LOW signals to the L298N input pins.
- The motor drivers receive motor power from the battery.
- ESP32 and both motor drivers share a common GND.

## Motor Driver #1 - Front Motors

| L298N #1 Pin | Connected To |
|---|---|
| OUT1 / OUT2 | Front Left Motor |
| OUT3 / OUT4 | Front Right Motor |
| IN1 | ESP32 GPIO 26 |
| IN2 | ESP32 GPIO 27 |
| IN3 | ESP32 GPIO 14 |
| IN4 | ESP32 GPIO 12 |
| 12V / VIN | Battery + |
| GND | Battery - / ESP32 GND |

## Motor Driver #2 - Rear Motors

| L298N #2 Pin | Connected To |
|---|---|
| OUT1 / OUT2 | Rear Left Motor |
| OUT3 / OUT4 | Rear Right Motor |
| IN1 | ESP32 GPIO 25 |
| IN2 | ESP32 GPIO 33 |
| IN3 | ESP32 GPIO 32 |
| IN4 | ESP32 GPIO 13 |
| 12V / VIN | Battery + |
| GND | Battery - / ESP32 GND |

## Notes

The 5V pins of the L298N modules are not used for ESP32 power.

ESP32 is powered separately through USB or a power bank.  
The L298N modules are powered by the external battery.

All GND lines must be connected together:

- ESP32 GND
- L298N #1 GND
- L298N #2 GND
- Battery -