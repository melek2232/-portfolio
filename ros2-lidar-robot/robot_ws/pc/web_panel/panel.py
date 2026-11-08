#!/usr/bin/env python3
"""PC web panel for the robot: live map, lidar, robot pose, teleoperation, modes, e-stop, click-to-go.

Run on the PC inside a ROS 2 Jazzy container (see pc/panel.sh), then open http://localhost:8080
It talks to the Pi over ROS 2 (same ROS_DOMAIN_ID).  Needs: rclpy, tf2_ros (both in ros-jazzy-desktop)."""
import argparse
import math
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_core import PanelState, make_server  # noqa: E402

import json  # noqa: E402

import rclpy  # noqa: E402
from geometry_msgs.msg import PoseStamped, Twist  # noqa: E402
from nav_msgs.msg import OccupancyGrid  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data  # noqa: E402
from sensor_msgs.msg import LaserScan  # noqa: E402
from std_msgs.msg import Bool, String  # noqa: E402
from tf2_ros import Buffer, TransformListener  # noqa: E402


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class PanelNode(Node):
    def __init__(self, state):
        super().__init__('robot_panel')
        self.state = state
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_teleop', 10)
        self.mode_pub = self.create_publisher(String, '/robot_mode', 10)
        self.estop_pub = self.create_publisher(Bool, '/estop', 10)
        self.goal_pub = self.create_publisher(PoseStamped, '/goal_pose', 10)
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, '/map', self.on_map, latched)
        self.create_subscription(LaserScan, '/scan_filtered', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(String, '/robot_state', lambda m: self.on_json(m, state.set_state), 10)
        self.create_subscription(String, '/robot_health', lambda m: self.on_json(m, state.set_health), 10)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.scan = None
        self.create_timer(0.1, self.update_pose)
        self.create_timer(0.25, self.update_scan)

    # ---- from the robot
    def on_json(self, msg, setter):
        try:
            setter(json.loads(msg.data))
        except ValueError:
            pass

    def on_map(self, m):
        # int8 -1 (unknown) becomes byte 255; 0..100 stay as they are
        self.state.set_map(m.info.width, m.info.height, m.info.resolution,
                           m.info.origin.position.x, m.info.origin.position.y,
                           bytes(bytearray(v & 0xFF for v in m.data)))

    def on_scan(self, m):
        self.scan = m

    def update_pose(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
            self.state.set_pose(t.transform.translation.x, t.transform.translation.y,
                                yaw_of(t.transform.rotation))
        except Exception:  # noqa: BLE001
            pass

    def update_scan(self):
        m = self.scan
        if m is None:
            return
        try:
            t = self.tf_buffer.lookup_transform('map', m.header.frame_id, rclpy.time.Time())
        except Exception:  # noqa: BLE001
            return
        tx, ty = t.transform.translation.x, t.transform.translation.y
        yaw = yaw_of(t.transform.rotation)
        c, s = math.cos(yaw), math.sin(yaw)
        pts = []
        for i in range(0, len(m.ranges), 2):
            r = m.ranges[i]
            if r != r or math.isinf(r) or r < m.range_min or r > m.range_max:
                continue
            a = m.angle_min + i * m.angle_increment
            x, y = r * math.cos(a), r * math.sin(a)
            pts.append([round(tx + c * x - s * y, 3), round(ty + s * x + c * y, 3)])
        self.state.set_scan(pts)

    # ---- to the robot (called by the HTTP handler)
    def send_cmd(self, v, w):
        v = max(-0.25, min(0.25, v))
        w = max(-1.5, min(1.5, w))
        msg = Twist()
        msg.linear.x, msg.angular.z = v, w
        self.cmd_pub.publish(msg)

    def set_mode(self, mode):
        self.mode_pub.publish(String(data=mode))

    def set_estop(self, on):
        self.estop_pub.publish(Bool(data=bool(on)))

    def send_goal(self, x, y, yaw):
        g = PoseStamped()
        g.header.frame_id = 'map'
        g.header.stamp = self.get_clock().now().to_msg()
        g.pose.position.x, g.pose.position.y = x, y
        g.pose.orientation.z, g.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        self.goal_pub.publish(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8080)
    ap.add_argument('--host', default='127.0.0.1')
    a = ap.parse_args()
    rclpy.init()
    state = PanelState()
    node = PanelNode(state)
    server = make_server(state, node, a.port, a.host)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f'Robot panel: open http://localhost:{a.port}   (Ctrl+C to quit)', flush=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.send_cmd(0.0, 0.0)
        except Exception:  # noqa: BLE001
            pass
        server.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
