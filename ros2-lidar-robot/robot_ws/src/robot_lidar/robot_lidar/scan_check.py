"""Prints a 1 Hz health report of the /scan topic (rate, valid points, nearest obstacle)."""
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class ScanCheck(Node):
    def __init__(self):
        super().__init__('scan_check')
        self.declare_parameter('topic', '/scan')
        topic = self.get_parameter('topic').value
        self.sub = self.create_subscription(
            LaserScan, topic, self.on_scan, qos_profile_sensor_data)
        self.count = 0
        self.last = None
        self.t0 = time.monotonic()
        self.create_timer(1.0, self.report)
        self.get_logger().info(f'Waiting for scans on {topic} ...')

    def on_scan(self, msg: LaserScan):
        self.count += 1
        self.last = msg

    def report(self):
        now = time.monotonic()
        rate = self.count / (now - self.t0)
        self.count, self.t0 = 0, now
        if self.last is None:
            self.get_logger().warning('No scan received yet (check port, baudrate, power).')
            return
        m = self.last
        valid = [(r, m.angle_min + i * m.angle_increment)
                 for i, r in enumerate(m.ranges)
                 if math.isfinite(r) and m.range_min <= r <= m.range_max]
        total = len(m.ranges)
        if not valid:
            self.get_logger().warning(f'{rate:.1f} Hz, 0/{total} valid points')
            return
        rmin, amin = min(valid)
        self.get_logger().info(
            f'{rate:.1f} Hz | {len(valid)}/{total} valid points | '
            f'nearest: {rmin:.2f} m at {math.degrees(amin):.0f} deg | '
            f'frame: {m.header.frame_id}')


def main():
    rclpy.init()
    node = ScanCheck()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
