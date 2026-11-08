# Arduino Mega firmware: `mega_motor_driver`

Raspberry Pi (USB cable) -> **Arduino Mega 2560** -> **H-bridge** -> motors.
The Mega only turns the pins: the Pi decides the PWM of the left and of the right side.
The motors stop by themselves if the Pi stops talking for 0.4 s.

## 1. Edit the CONFIG block of `mega_motor_driver/mega_motor_driver.ino`
| Setting | Meaning |
|---|---|
| `DRIVER_TYPE 1` | H-bridge with **EN + IN1 + IN2** per side: L298N, L293D, TB6612, VNH2SP30 (default) |
| `DRIVER_TYPE 2` | H-bridge with **RPWM + LPWM** per side: BTS7960 / IBT-2, DRV8871 |
| `L_IN1 L_IN2 L_PWM` ... | pins used on the Mega (PWM-capable pins: 2 to 13 and 44 to 46) |
| `WATCHDOG_MS` | stop delay without command (400 ms) |
| `ENCODERS 1` | enables wheel encoders (see below), `0` = none |

The defaults assume this wiring. **If yours differs, change the numbers, not the wires.**

### L298N (type 1)
| L298N | Mega | |
|---|---|---|
| IN1 / IN2 (left) | D22 / D23 | direction |
| ENA (left) | D5 | PWM. **Remove the ENA jumper** on the module |
| IN3 / IN4 (right) | D24 / D25 | direction |
| ENB (right) | D6 | PWM. **Remove the ENB jumper** |
| GND | GND of the Mega | **common ground is mandatory** |
| 12V / battery + | motor battery | not from the Pi or the Mega |

The two motors of the left side are wired **in parallel** on OUT1/OUT2, those of the right
side on OUT3/OUT4. Check that the sum of their stall currents stays below the driver rating
(L298N: 2 A per channel; a BTS7960 module handles much more).

### BTS7960 (type 2): one module per side
| BTS7960 | Mega left / right |
|---|---|
| RPWM | D5 / D6 |
| LPWM | D4 / D7 |
| R_EN, L_EN | D22, D23 / D24, D25 (set HIGH by the sketch), or tie them to 5 V |
| VCC, GND | 5 V, GND (common ground) |
| B+, B- | motor battery |

## 2. Upload
Arduino IDE -> Tools -> Board: **Arduino Mega or Mega 2560**, Processor: ATmega2560 -> Upload.
The Mega is powered by the USB cable from the Pi; the motors by their own battery.

## 3. Check the wiring without ROS (robot ON BLOCKS)
```bash
sudo apt install python3-serial
python3 firmware/tools/arduino_test.py /dev/ttyACM0
```
It runs left / right / both forward / both backward / turn, then checks the watchdog.
* wrong **side** moves: swap the two wires of that motor pair, or change the pins in the sketch;
* a side turns **backward** while "forward" is expected: set `invert_left` / `invert_right`
  to `true` in `src/robot_base/config/base.yaml` (do **not** swap wires and invert both).

Find the port: `ls -l /dev/serial/by-id/`. The Mega is `/dev/ttyACM0` (original board) or
`/dev/ttyUSB0` (CH340 clone), and the lidar is usually `/dev/ttyUSB0` too: if both are
`ttyUSB*`, use the `by-id` paths (they never swap): `serial_port:=/dev/serial/by-id/usb-...`.

## 4. Optional: wheel encoders (better odometry, better maps)
Set `ENCODERS 1`, wire channel A of each encoder to an **interrupt pin** (`ENC_L_A` = 18,
`ENC_R_A` = 19) and channel B to `ENC_L_B` = 31, `ENC_R_B` = 33, power them with 5 V / GND, re-upload.
The Mega then sends `T <left> <right>` every 50 ms. On the Pi set in `base.yaml`:
`use_encoders: true`, `ticks_per_meter_left/right` and `encoder_invert_left/right: true`
if the ticks decrease when the robot goes forward. To get `ticks_per_meter`, stop ROS, run
`python3 firmware/tools/read_ticks.py /dev/ttyACM0`, push the robot exactly 1 m by hand, and note
the left and right numbers.

## Protocol (115200 8N1, text lines)
`M <left> <right>` (PWM -255..255), `S` stop, `P` ping -> `PONG`, `Z` reset encoders.
Replies: `# mega_motor_driver ready` at boot, `T l r` with encoders, `? <line>` if not understood.

## Tests on a PC (no Arduino needed)
`firmware/host_test/run_tests.sh` compiles the sketch with stand-ins for the Arduino functions
and checks pins, clamping, watchdog and parsing. It does **not** replace uploading to the board.
