#!/usr/bin/env python3
"""Measures odometry drift in the simulator: compares /odom with /ground_truth (fake_robot.py).

  ros2 launch robot_description sim_lite.launch.py odom:=lidar slip_linear:=0.9 slip_angular:=0.8 rviz:=false
  ros2 run robot_description eval_odom.py --duration 120
Prints driven distance, final position / heading error, and drift as % of distance.
Both start at (0, 0, 0), so they are directly comparable.  --json prints one line for scripts.
"""
import argparse
import json
import math
import sys
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


class Eval(Node):
    def __init__(self):
        super().__init__('eval_odom')
        self.odom = self.truth = None
        self.dist = 0.0
        self.last_truth_xy = None
        self.max_err = 0.0
        self.samples = 0
        self.create_subscription(Odometry, '/odom', self.on_odom, qos_profile_sensor_data)
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, 10)

    def on_odom(self, m):
        self.odom = m.pose.pose

    def on_truth(self, m):
        self.truth = m.pose.pose
        xy = (m.pose.pose.position.x, m.pose.pose.position.y)
        if self.last_truth_xy:
            self.dist += math.dist(xy, self.last_truth_xy)
        self.last_truth_xy = xy
        if self.odom is not None:
            self.samples += 1
            self.max_err = max(self.max_err, self.errors()[0])

    def errors(self):
        o, t = self.odom, self.truth
        e_xy = math.hypot(o.position.x - t.position.x, o.position.y - t.position.y)
        e_yaw = abs(wrap(yaw_of(o.orientation) - yaw_of(t.orientation)))
        return e_xy, e_yaw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration', type=float, default=60.0, help='seconds')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    rclpy.init()
    n = Eval()
    end = None
    while rclpy.ok():
        rclpy.spin_once(n, timeout_sec=0.1)
        if end is None and n.odom is not None and n.truth is not None:
            end = time.monotonic() + a.duration
        if end is not None and time.monotonic() > end:
            break
    if n.odom is None or n.truth is None:
        print('no /odom or /ground_truth received', file=sys.stderr)
        return 1
    e_xy, e_yaw = n.errors()
    res = dict(seconds=a.duration, distance_m=round(n.dist, 2), final_error_m=round(e_xy, 3),
               max_error_m=round(n.max_err, 3), final_heading_error_deg=round(math.degrees(e_yaw), 1),
               drift_percent=round(100.0 * e_xy / n.dist, 1) if n.dist > 0.1 else None,
               samples=n.samples)
    if a.json:
        print(json.dumps(res))
    else:
        print(f"{res['distance_m']} m driven in {a.duration:.0f} s: final error {res['final_error_m']} m "
              f"({res['drift_percent']} % of distance), max {res['max_error_m']} m, "
              f"heading {res['final_heading_error_deg']} deg")
    n.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
