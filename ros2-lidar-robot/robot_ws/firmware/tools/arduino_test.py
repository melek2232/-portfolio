#!/usr/bin/env python3
"""Wiring test of the Arduino Mega + H-bridge, WITHOUT ROS. Only needs pyserial.

   python3 arduino_test.py /dev/ttyACM0            (use --yes to skip the confirmations)

PUT THE ROBOT ON BLOCKS (wheels in the air) the first time.
Each step turns one group of wheels for a couple of seconds. Look at what really happens:
  * a wrong SIDE         -> swap the two motor wires of that side, or change the pins in the sketch
  * a side turns BACKWARD-> set invert_left / invert_right to true in robot_base/config/base.yaml
"""
import argparse
import sys
import time

import serial

STEPS = [
    ('LEFT side only, forward', 1, 0),
    ('RIGHT side only, forward', 0, 1),
    ('BOTH sides forward  (the robot would drive FORWARD)', 1, 1),
    ('BOTH sides backward', -1, -1),
    ('turn in place to the LEFT (left side back, right side forward)', -1, 1),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('port', nargs='?', default='/dev/ttyACM0')
    ap.add_argument('--duty', type=int, default=90, help='PWM 0..255 (default 90)')
    ap.add_argument('--seconds', type=float, default=2.0)
    ap.add_argument('--yes', action='store_true', help='do not ask before each step')
    a = ap.parse_args()
    duty = max(0, min(255, a.duty))

    ser = serial.Serial(a.port, 115200, timeout=0.2)
    print(f'opened {a.port}, waiting for the Mega to restart ...')
    time.sleep(2.5)
    boot = ser.read(200).decode('ascii', 'ignore').strip()
    print('Mega says:', boot or '(nothing: wrong port, or the sketch is not uploaded)')
    ser.write(b'P\n')
    pong = ser.readline().decode('ascii', 'ignore').strip()
    print('ping ->', pong or '(no answer)')
    if 'PONG' not in pong:
        print('The Mega does not answer. Check the port and that mega_motor_driver.ino is uploaded.')
        return 1

    try:
        for name, l, r in STEPS:
            if not a.yes:
                input(f'\n[Enter] to run: {name} ')
            else:
                print(f'\n{name}')
            t0 = time.monotonic()
            while time.monotonic() - t0 < a.seconds:
                ser.write(f'M {l * duty} {r * duty}\n'.encode())
                time.sleep(0.1)
            ser.write(b'S\n')
            time.sleep(0.5)
        print('\nDone. Watchdog check: sending one command and then nothing ...')
        ser.write(f'M {duty} {duty}\n'.encode())
        print('The wheels must stop by themselves within about half a second.')
        time.sleep(1.5)
    finally:
        ser.write(b'S\n')
        ser.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
