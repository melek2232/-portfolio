"""Cleans the lidar scan before SLAM and the safety layer use it.

/scan  ->  /scan_filtered
  * invalid beams (0, NaN, outside [range_min, range_max]) become inf
  * isolated points ("speckle": no neighbour at a similar distance within a small angle) are removed.
    They create ghost obstacles and blur walls in the map.
"""
import math

INF = float('inf')


def filter_ranges(ranges, a_inc, r_min, r_max, despeckle=True, win_angle=0.04,
                  tol_abs=0.06, tol_rel=0.04, min_neighbors=1):
    n = len(ranges)
    valid = [(r == r) and (not math.isinf(r)) and r_min <= r <= r_max for r in ranges]
    out = [INF] * n
    win = max(1, int(round(win_angle / a_inc))) if a_inc > 0 else 2
    for i in range(n):
        if not valid[i]:
            continue
        if not despeckle:
            out[i] = ranges[i]
            continue
        tol = max(tol_abs, tol_rel * ranges[i])
        cnt = 0
        for j in range(max(0, i - win), min(n, i + win + 1)):
            if j != i and valid[j] and abs(ranges[j] - ranges[i]) <= tol:
                cnt += 1
                if cnt >= min_neighbors:
                    break
        if cnt >= min_neighbors:
            out[i] = ranges[i]
    return out


try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan
except ImportError:      # logic can be tested without ROS
    rclpy = None
    Node = object


class ScanFilterNode(Node):
    def __init__(self):
        super().__init__('scan_filter')
        d = self.declare_parameter
        d('input_topic', '/scan')
        d('output_topic', '/scan_filtered')
        d('range_min', 0.12)
        d('range_max', 8.0)
        d('despeckle', True)
        d('win_angle', 0.04)
        d('tol_abs', 0.06)
        d('tol_rel', 0.04)
        self.pub = self.create_publisher(LaserScan, self.p('output_topic'), qos_profile_sensor_data)
        self.create_subscription(LaserScan, self.p('input_topic'), self.on_scan, qos_profile_sensor_data)

    def p(self, name):
        return self.get_parameter(name).value

    def on_scan(self, msg):
        r_min = max(float(self.p('range_min')), float(msg.range_min))
        r_max = min(float(self.p('range_max')), float(msg.range_max)) if msg.range_max > 0 \
            else float(self.p('range_max'))
        out = LaserScan()
        out.header = msg.header
        out.angle_min = msg.angle_min
        out.angle_max = msg.angle_max
        out.angle_increment = msg.angle_increment
        out.time_increment = msg.time_increment
        out.scan_time = msg.scan_time
        out.range_min = r_min
        out.range_max = r_max
        out.ranges = filter_ranges(list(msg.ranges), msg.angle_increment, r_min, r_max,
                                   bool(self.p('despeckle')), float(self.p('win_angle')),
                                   float(self.p('tol_abs')), float(self.p('tol_rel')))
        self.pub.publish(out)


def main():
    rclpy.init()
    node = ScanFilterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
