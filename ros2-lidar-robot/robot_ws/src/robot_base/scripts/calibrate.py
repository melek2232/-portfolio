#!/usr/bin/env python3
"""Interactive calibration, on the Pi with the robot running (./run_robot.sh) in an open area.

  ./src/robot_base/scripts/calibrate.py straight     drives 5 s straight, you measure the distance
  ./src/robot_base/scripts/calibrate.py turn         rotates 5 s in place, you estimate the angle
It only PRINTS the values to put in src/robot_base/config/base.yaml (then restart ./run_robot.sh).
Robot on the floor, 1.5 m of free space ahead for 'straight', a hand near the power switch."""
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_YAML = os.path.join(HERE, '..', 'config', 'base.yaml')


def read_param(name, default):
    try:
        with open(BASE_YAML) as f:
            m = re.search(rf'^\s*{name}:\s*([0-9.eE+-]+)', f.read(), re.M)
        return float(m.group(1)) if m else default
    except OSError:
        return default


def suggest_straight(max_wheel_speed, v, seconds, measured_m):
    """Real speed ~ proportional to 1/max_wheel_speed, so scale it by (measured / expected)."""
    ratio = measured_m / (v * seconds)
    return ratio, max_wheel_speed * ratio


def suggest_turn(w, seconds, measured_deg):
    ratio = measured_deg / math.degrees(w * seconds)
    return ratio


def publish(topic, v, w, seconds, hz=10):
    msg = f'{{linear: {{x: {v}}}, angular: {{z: {w}}}}}'
    subprocess.run(['ros2', 'topic', 'pub', '--times', str(int(seconds * hz)), '-r', str(hz),
                    topic, 'geometry_msgs/msg/Twist', msg], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def set_manual():
    subprocess.run(['ros2', 'topic', 'pub', '--once', '/robot_mode', 'std_msgs/msg/String',
                    '{data: manual}'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('straight', 'turn'):
        print(__doc__)
        return 1
    set_manual()
    if sys.argv[1] == 'straight':
        v, seconds = 0.15, 5.0
        input(f'Mark the start of the front wheels with tape, keep {v * seconds + 0.5:.1f} m free ahead. Enter to drive...')
        publish('/cmd_vel_teleop', v, 0.0, seconds)
        d = float(input('Distance travelled in metres (measure it): ').replace(',', '.'))
        M = read_param('max_wheel_speed', 0.30)
        ratio, new_m = suggest_straight(M, v, seconds, d)
        print(f'\nCommanded {v * seconds:.2f} m, measured {d:.2f} m (ratio {ratio:.2f}).')
        print(f'In base.yaml set:   max_wheel_speed: {new_m:.3f}     (now {M})')
        print('Repeat until the ratio is close to 1. If the robot did not move, raise min_duty first.')
    else:
        w, seconds = 0.6, 5.0
        input(f'Put a mark on the floor along the robot axis. It will turn {math.degrees(w * seconds):.0f} deg. Enter...')
        publish('/cmd_vel_teleop', 0.0, w, seconds)
        deg = float(input('Angle really turned in degrees (estimate against the mark): ').replace(',', '.'))
        ratio = suggest_turn(w, seconds, deg)
        print(f'\nCommanded {math.degrees(w * seconds):.0f} deg, turned {deg:.0f} deg (ratio {ratio:.2f}).')
        print(f'In base.yaml set:   angular_scale: {ratio:.2f}     (this corrects the odometry used by SLAM)')
        if ratio < 0.6:
            print('The robot turns much less than commanded: raise min_duty (or the turn speed of the explorer).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
