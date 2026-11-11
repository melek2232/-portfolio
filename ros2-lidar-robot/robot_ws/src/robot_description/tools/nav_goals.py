#!/usr/bin/env python3
"""Sends Nav2 NavigateToPose goals and checks, against /ground_truth, where the robot really ended.

  ros2 launch robot_description sim_lite.launch.py odom:=lidar nav:=true rviz:=false
  ros2 run robot_description nav_goals.py                     # default tour of the simulated room
  ros2 run robot_description nav_goals.py --goal 1.0 0.5 --goal 0 0
The map frame of the live SLAM map starts at the robot's start pose, like /ground_truth, so the
real error is |truth - goal|. Exit code 0 only if every goal succeeded within --tolerance.
"""
import argparse
import json
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node

# tour of worlds/mapping_room.sdf from the start pose (0, 0): around the box, along the inner walls,
# then behind the long wall (x = -1.6 m, unexplored at start) and back
DEFAULT_TOUR = [(1.5, 0.0), (1.2, 2.0), (-1.0, 2.0), (-0.5, -0.7), (-3.0, 0.5), (0.0, 0.0)]


class Goals(Node):
    def __init__(self):
        super().__init__('nav_goals')
        self.truth = None
        self.create_subscription(Odometry, '/ground_truth', self.on_truth, 10)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def on_truth(self, m):
        self.truth = (m.pose.pose.position.x, m.pose.pose.position.y)

    def wait(self, fut, timeout):
        end = time.monotonic() + timeout
        while rclpy.ok() and not fut.done() and time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.1)
        return fut.done()

    def go(self, x, y, yaw, timeout):
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x, goal.pose.pose.position.y = x, y
        goal.pose.pose.orientation.z, goal.pose.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        t0 = time.monotonic()
        send = self.client.send_goal_async(goal)
        if not self.wait(send, 10.0) or not send.result().accepted:
            return dict(goal=[x, y], status='rejected')
        handle = send.result()
        res = handle.get_result_async()
        if not self.wait(res, timeout):
            handle.cancel_goal_async()
            status = 'timeout'
        else:
            status = {4: 'succeeded', 5: 'canceled', 6: 'aborted'}.get(res.result().status,
                                                                      str(res.result().status))
        for _ in range(5):
            rclpy.spin_once(self, timeout_sec=0.1)
        err = math.hypot(self.truth[0] - x, self.truth[1] - y) if self.truth else None
        return dict(goal=[x, y], status=status, seconds=round(time.monotonic() - t0, 1),
                    true_error_m=round(err, 3) if err is not None else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--goal', nargs=2, type=float, action='append', metavar=('X', 'Y'))
    ap.add_argument('--timeout', type=float, default=120.0, help='seconds per goal')
    ap.add_argument('--tolerance', type=float, default=0.25, help='max true error, m')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    rclpy.init()
    n = Goals()
    if not n.client.wait_for_server(timeout_sec=60.0):
        print('navigate_to_pose action server not available (is Nav2 active?)', file=sys.stderr)
        return 2
    results = []
    for x, y in a.goal or DEFAULT_TOUR:
        r = n.go(x, y, 0.0, a.timeout)
        results.append(r)
        if not a.json:
            print(f"goal ({x:+.2f}, {y:+.2f}): {r['status']}  {r.get('seconds', '-')} s  "
                  f"true error {r.get('true_error_m')} m")
    ok = all(r['status'] == 'succeeded' and r.get('true_error_m') is not None
             and r['true_error_m'] <= a.tolerance for r in results)
    if a.json:
        print(json.dumps(dict(ok=ok, goals=results)))
    else:
        print('PASS' if ok else 'FAIL', f'{sum(r["status"] == "succeeded" for r in results)}/{len(results)} goals')
    n.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
