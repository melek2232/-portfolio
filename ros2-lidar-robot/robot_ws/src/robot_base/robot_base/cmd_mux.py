"""ROS node around mux.Mux: picks the command source by mode, applies the safety layer,
publishes /cmd_vel_safe (to base_node) and /robot_state (JSON, for the PC panel and health)."""
import json
import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String

from .mux import Mux, corridor_clearance


class CmdMuxNode(Node):
    def __init__(self):
        super().__init__('cmd_mux')
        d = self.declare_parameter
        d('initial_mode', 'manual')
        d('source_timeout', 0.5)
        d('scan_timeout', 1.0)
        d('scan_topic', '/scan_filtered')
        d('lidar_yaw', 0.0)            # same as the lidar_yaw launch argument
        d('front_offset', 0.205)       # lidar -> front of the body, m
        d('rear_offset', 0.081)        # lidar -> rear of the body, m
        d('half_width', 0.075)
        d('side_margin', 0.05)
        d('stop_distance', 0.10)       # body to obstacle, m
        d('slow_distance', 0.45)
        d('block_when_blind', True)
        d('max_linear', 0.20)
        d('max_angular', 1.2)
        d('rate_hz', 20.0)
        keys = ('initial_mode', 'source_timeout', 'scan_timeout', 'stop_distance', 'slow_distance',
                'block_when_blind', 'max_linear', 'max_angular')
        self.mux = Mux(**{k: self.p(k) for k in keys})

        self.out = self.create_publisher(Twist, '/cmd_vel_safe', 10)
        self.state_pub = self.create_publisher(String, '/robot_state', 10)
        self.create_subscription(Twist, '/cmd_vel_teleop', lambda m: self.on_cmd('manual', m), 10)
        self.create_subscription(Twist, '/cmd_vel_auto', lambda m: self.on_cmd('explore', m), 10)
        self.create_subscription(Twist, '/cmd_vel', lambda m: self.on_cmd('nav', m), 10)
        self.create_subscription(String, '/robot_mode', self.on_mode, 10)
        self.create_subscription(Bool, '/estop', self.on_estop, 10)
        self.create_subscription(LaserScan, self.p('scan_topic'), self.on_scan, qos_profile_sensor_data)
        self.create_timer(1.0 / float(self.p('rate_hz')), self.tick)
        self.create_timer(0.2, self.publish_state)
        self.last_info = {}
        self.get_logger().info(f'cmd_mux ready, mode={self.mux.mode}')

    def p(self, name):
        return self.get_parameter(name).value

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_cmd(self, source, msg):
        self.mux.on_cmd(source, msg.linear.x, msg.angular.z, self.now())

    def on_mode(self, msg):
        old = self.mux.mode
        if self.mux.set_mode(msg.data):
            if old != self.mux.mode:
                self.get_logger().info(f'mode: {old} -> {self.mux.mode}')
        else:
            self.get_logger().warning(f'mode "{msg.data}" refused (unknown, or e-stop active)')

    def on_estop(self, msg):
        was = self.mux.estopped
        self.mux.set_estop(bool(msg.data))
        if bool(msg.data) != was:
            self.get_logger().warning('E-STOP ACTIVE' if msg.data else 'e-stop released (mode: stop)')

    def on_scan(self, msg):
        yaw = float(self.p('lidar_yaw'))
        front, rear = corridor_clearance(
            msg.ranges, msg.angle_min + yaw, msg.angle_increment,
            max(msg.range_min, 0.05), msg.range_max if msg.range_max > 0 else 8.0,
            float(self.p('front_offset')), float(self.p('rear_offset')),
            float(self.p('half_width')), float(self.p('side_margin')))
        self.mux.on_clearance(front, rear, self.now())

    def tick(self):
        v, w, info = self.mux.step(self.now())
        cmd = Twist()
        cmd.linear.x = float(v)
        cmd.angular.z = float(w)
        self.out.publish(cmd)
        info['v'], info['w'] = v, w
        if info.get('reason') != self.last_info.get('reason') and info['reason'] in ('blind', 'obstacle'):
            self.get_logger().warning(f'motion limited: {info["reason"]} '
                                      f'(front {info["front"]:.2f} m, rear {info["rear"]:.2f} m)')
        self.last_info = info

    def publish_state(self):
        i = dict(self.last_info)
        for k in ('front', 'rear'):
            if k in i and (i[k] is None or math.isinf(i[k])):
                i[k] = None
        self.state_pub.publish(String(data=json.dumps(i)))


def main():
    rclpy.init()
    node = CmdMuxNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.out.publish(Twist())
        except Exception:  # noqa: BLE001
            pass
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
