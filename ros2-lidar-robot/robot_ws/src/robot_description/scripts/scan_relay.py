#!/usr/bin/env python3
"""Relays /scan_raw (from Gazebo) to /scan and forces the frame_id to lidar_link."""
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class ScanRelay(Node):
    def __init__(self):
        super().__init__('scan_relay')
        self.declare_parameter('frame_id', 'lidar_link')
        self.frame = self.get_parameter('frame_id').value
        self.pub = self.create_publisher(LaserScan, '/scan', qos_profile_sensor_data)
        self.create_subscription(LaserScan, '/scan_raw', self.on_scan, qos_profile_sensor_data)

    def on_scan(self, msg):
        msg.header.frame_id = self.frame
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = ScanRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
