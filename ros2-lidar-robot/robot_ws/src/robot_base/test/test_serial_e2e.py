#!/usr/bin/env python3
"""End-to-end test WITHOUT ROS and WITHOUT hardware.

The real Mega sketch is compiled as a PC program and connected to the Pi-side SerialMotors
class through a pseudo-terminal. Checks: commands reach the pins, keep-alive, watchdog,
inversion, stop, encoder ticks.   Usage: python3 test_serial_e2e.py   (needs g++ and pyserial)
"""
import os
import subprocess
import sys
import time
import tty

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..'))
from robot_base.motors import SerialMotors  # noqa: E402

HT = os.path.join(WS, 'firmware', 'host_test')
SKETCH = os.path.join(WS, 'firmware', 'mega_motor_driver', 'mega_motor_driver.ino')


class Log:
    def info(self, m): print('  [info]', m)
    def warn(self, m): print('  [warn]', m)
    warning = warn
    def error(self, m): print('  [error]', m)


def build(encoders):
    src = open(SKETCH).read()
    if encoders:
        src = src.replace('#define ENCODERS 0', '#define ENCODERS 1')
    tmp = f'/tmp/sim_sketch_{int(encoders)}.ino'
    open(tmp, 'w').write(src)
    main = open(os.path.join(HT, 'sim_main.cpp')).read().replace(
        '"../mega_motor_driver/mega_motor_driver.ino"', f'"{tmp}"')
    cpp = f'/tmp/sim_main_{int(encoders)}.cpp'
    open(cpp, 'w').write(main)
    exe = f'/tmp/sim_mega_{int(encoders)}'
    subprocess.check_call(['g++', '-std=c++11', '-DHOST_STDIN', '-I' + HT, cpp,
                           os.path.join(HT, 'host_stubs.cpp'), '-o', exe])
    return exe


def start(exe, pinlog):
    master, slave = os.openpty()
    tty.setraw(slave)                       # no echo / line editing on the fake serial line
    proc = subprocess.Popen([exe], stdin=master, stdout=master,
                            env=dict(os.environ, PIN_LOG=pinlog))
    return proc, master, slave, os.ttyname(slave)


def last_pins(pinlog):
    rows = [ln.split() for ln in open(pinlog).read().splitlines() if ln.strip()]
    return (int(rows[-1][1]), int(rows[-1][2])) if rows else None


fails = 0


def check(name, cond):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name)
    fails += 0 if cond else 1


def main():
    exe = build(False)
    pinlog = '/tmp/sim_pins.log'
    open(pinlog, 'w').close()
    proc, master, slave, port = start(exe, pinlog)
    try:
        m = SerialMotors(port, 115200, False, False, Log(), boot_wait=0.2)
        m.set(0.5, -0.25); time.sleep(0.15)
        check('duty 0.5/-0.25 -> M 128 -64 on the pins', last_pins(pinlog) == (128, -64))

        t0 = time.monotonic()
        while time.monotonic() - t0 < 1.0:                       # keep-alive well past the watchdog
            m.set(0.5, -0.25); time.sleep(0.05)
        check('keep-alive: still running after 1 s', last_pins(pinlog) == (128, -64))

        time.sleep(0.7)                                          # no more commands
        check('watchdog stops the motors', last_pins(pinlog) == (0, 0))

        m.set(1.0, 1.0); time.sleep(0.15)
        check('full duty -> 255/255', last_pins(pinlog) == (255, 255))
        m.stop(); time.sleep(0.15)
        check('stop() -> 0/0', last_pins(pinlog) == (0, 0))
        m.set(3.0, -3.0); time.sleep(0.15)
        check('values above 1 are clamped', last_pins(pinlog) == (255, -255))
        m.close(); time.sleep(0.15)
        check('close() stops the motors', last_pins(pinlog) == (0, 0))

        m = SerialMotors(port, 115200, True, False, Log(), boot_wait=0.2)
        m.set(0.4, 0.4); time.sleep(0.15)
        check('invert_left flips only the left side', last_pins(pinlog) == (-102, 102))
        m.close()
    finally:
        proc.kill(); proc.wait()

    # encoder build: the firmware streams "T l r"
    exe = build(True)
    open(pinlog, 'w').close()
    proc, master, slave, port = start(exe, pinlog)
    try:
        m = SerialMotors(port, 115200, False, False, Log(), boot_wait=0.2)
        time.sleep(0.3)
        tk = m.ticks()
        check('encoder ticks received', tk is not None and tk[0] == 0 and tk[1] == 0)
        t1 = tk[2] if tk else 0
        time.sleep(0.2)
        tk2 = m.ticks()
        check('encoder ticks keep coming', tk2 is not None and tk2[2] > t1)
        m.close()
    finally:
        proc.kill(); proc.wait()

    # a port that does not exist must fail loudly at start-up
    try:
        SerialMotors('/dev/does_not_exist', 115200, False, False, Log(), boot_wait=0.0)
        check('missing port raises', False)
    except Exception:
        check('missing port raises', True)

    print('ALL PASSED' if not fails else f'{fails} FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
