#!/usr/bin/env python3
"""Prints the encoder ticks of the Mega (firmware with ENCODERS 1). Pyserial only, no ROS.

   python3 read_ticks.py /dev/ttyACM0
Push the robot exactly 1 m by hand and note the final numbers: they are ticks_per_meter_left/right
(Ctrl+C to quit; stop ROS first, only one program can use the port).
"""
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyACM0'
ser = serial.Serial(port, 115200, timeout=0.5)
time.sleep(2.5)
ser.write(b'Z\n')                     # counters back to 0
print('counters reset; push the robot, Ctrl+C to quit')
try:
    while True:
        line = ser.readline().decode('ascii', 'ignore').strip()
        if line.startswith('T '):
            print('\rleft/right ticks:', line[2:], '      ', end='', flush=True)
except KeyboardInterrupt:
    print()
