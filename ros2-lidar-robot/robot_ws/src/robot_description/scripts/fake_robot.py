#!/usr/bin/env python3
"""Simulated robot WITHOUT Gazebo: a ray-cast lidar in the room of worlds/mapping_room.sdf.

Publishes /scan (frame lidar_link), /odom, TF odom->base_link and /joint_states, exactly like the
real robot does, so slam_toolbox, Nav2 and RViz run unchanged.  It drives itself (the same explorer as
Gazebo) or follows /cmd_vel (parameter auto:=false, drive with teleop_twist_keyboard).
Needs only ROS 2 and numpy; no GPU, so it works in a virtual machine.

Odometry modes (parameter odom_mode), to compare odometry sources against the truth:
  truth      /odom + TF are the exact pose (ideal encoders)                       [default]
  open_loop  /odom + TF integrate the COMMANDED speeds, like base_node without encoders,
             while the robot really moves with wheel slip (slip_linear, slip_angular)
  none       no /odom and no TF: another node provides them (lidar odometry, rf2o)
The true pose is always published on /ground_truth (nav_msgs/Odometry, frame 'odom') for evaluation.
"""
import math
import os
import random
import sys

import numpy as np
import rclpy
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState, LaserScan
from tf2_ros import TransformBroadcaster

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import offline_check as oc  # noqa: E402  (installed next to this file)

WHEELS = ['leftrearwheel', 'rightrearwheel', 'left_front_wheel_joint', 'rightfrontwheel']


class FakeRobot(Node):
    def __init__(self):
        super().__init__('fake_robot')
        self.declare_parameter('auto', True)
        self.declare_parameter('noise', 0.01)         # lidar range noise, metres
        self.declare_parameter('seed', 1)
        self.declare_parameter('odom_mode', 'truth')  # truth | open_loop | none
        self.declare_parameter('slip_linear', 1.0)    # real distance / commanded distance
        self.declare_parameter('slip_angular', 1.0)   # real rotation / commanded rotation (skid-steer < 1)
        self.odom_mode = str(self.get_parameter('odom_mode').value)
        if self.odom_mode not in ('truth', 'open_loop', 'none'):
            raise ValueError(f"odom_mode must be truth, open_loop or none, not '{self.odom_mode}'")
        self.slip_v = float(self.get_parameter('slip_linear').value)
        self.slip_w = float(self.get_parameter('slip_angular').value)
        self.auto = self.get_parameter('auto').value
        self.noise = self.get_parameter('noise').value
        oc.WORLD = os.path.join(get_package_share_directory('robot_description'),
                                'worlds', 'mapping_room.sdf')
        self.occ, _ = oc.build_world()
        self.logic = oc.wander.Wanderer(rng=random.Random(self.get_parameter('seed').value))
        self.x = self.y = self.yaw = 0.0
        self.ox = self.oy = self.oyaw = 0.0               # open-loop estimate (odom_mode open_loop)
        self.cmd = (0.0, 0.0)
        self.cmd_time = 0.0
        self.t = 0.0
        self.scan_pub = self.create_publisher(LaserScan, '/scan', qos_profile_sensor_data)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.truth_pub = self.create_publisher(Odometry, '/ground_truth', 10)
        self.js_pub = self.create_publisher(JointState, '/joint_states', 10)
        self.tf = TransformBroadcaster(self)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd, 10)
        self.dt = 0.1
        self.create_timer(self.dt, self.step)
        self.get_logger().info(f'fake_robot: simulated room, lidar on /scan, odom_mode={self.odom_mode}, '
                               f'slip={self.slip_v:.2f}/{self.slip_w:.2f}, truth on /ground_truth')

    def on_cmd(self, msg):
        self.cmd = (msg.linear.x, msg.angular.z)
        self.cmd_time = self.t

    def step(self):
        lx = self.x + math.cos(self.yaw) * oc.LIDAR_X
        ly = self.y + math.sin(self.yaw) * oc.LIDAR_X
        rng, _ = oc.scan(self.occ, lx, ly, self.yaw)
        rng = rng + np.random.normal(0.0, self.noise, rng.shape)
        if self.auto:
            v, w = self.logic.step(rng.tolist(), -math.pi, 2 * math.pi / oc.BEAMS,
                                   oc.R_MIN, oc.R_MAX, self.t)
        else:
            v, w = self.cmd if self.t - self.cmd_time < 0.5 else (0.0, 0.0)
        cmd_v, cmd_w = v, w
        v, w = v * self.slip_v, w * self.slip_w           # what the wheels really achieve
        nyaw = self.yaw + w * self.dt
        nx = self.x + v * math.cos(self.yaw) * self.dt
        ny = self.y + v * math.sin(self.yaw) * self.dt
        if oc.body_collides(self.occ, nx, ny, nyaw):
            v = w = 0.0                                  # blocked by a wall
        else:
            self.x, self.y, self.yaw = nx, ny, nyaw
        # open-loop estimate: integrates the commands, knows nothing about slip or walls (like base_node)
        self.oyaw += cmd_w * self.dt
        self.ox += cmd_v * math.cos(self.oyaw) * self.dt
        self.oy += cmd_v * math.sin(self.oyaw) * self.dt
        self.t += self.dt
        now = self.get_clock().now().to_msg()

        scan = LaserScan()
        scan.header.stamp = now
        scan.header.frame_id = 'lidar_link'
        scan.angle_min = -math.pi
        scan.angle_max = math.pi - 2 * math.pi / oc.BEAMS
        scan.angle_increment = 2 * math.pi / oc.BEAMS
        scan.time_increment = 0.0
        scan.scan_time = self.dt
        scan.range_min = oc.R_MIN
        scan.range_max = oc.R_MAX
        scan.ranges = [float(r) if oc.R_MIN <= r <= oc.R_MAX else float('inf') for r in rng]
        self.scan_pub.publish(scan)

        self.truth_pub.publish(self.odometry(now, self.x, self.y, self.yaw, v, w))
        if self.odom_mode != 'none':
            if self.odom_mode == 'open_loop':
                ex, ey, eyaw, ev, ew = self.ox, self.oy, self.oyaw, cmd_v, cmd_w
            else:
                ex, ey, eyaw, ev, ew = self.x, self.y, self.yaw, v, w
            qz, qw = math.sin(eyaw / 2), math.cos(eyaw / 2)
            tf = TransformStamped()
            tf.header.stamp = now
            tf.header.frame_id = 'odom'
            tf.child_frame_id = 'base_link'
            tf.transform.translation.x = ex
            tf.transform.translation.y = ey
            tf.transform.rotation.z = qz
            tf.transform.rotation.w = qw
            self.tf.sendTransform(tf)
            self.odom_pub.publish(self.odometry(now, ex, ey, eyaw, ev, ew))

        js = JointState()
        js.header.stamp = now
        js.name = WHEELS
        js.position = [0.0] * len(WHEELS)
        self.js_pub.publish(js)


    @staticmethod
    def odometry(stamp, x, y, yaw, v, w):
        od = Odometry()
        od.header.stamp = stamp
        od.header.frame_id = 'odom'
        od.child_frame_id = 'base_link'
        od.pose.pose.position.x = x
        od.pose.pose.position.y = y
        od.pose.pose.orientation.z = math.sin(yaw / 2)
        od.pose.pose.orientation.w = math.cos(yaw / 2)
        od.twist.twist.linear.x = v
        od.twist.twist.angular.z = w
        return od


def main():
    rclpy.init()
    node = FakeRobot()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
