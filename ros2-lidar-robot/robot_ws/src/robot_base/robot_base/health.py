"""Watches the robot and publishes /robot_health (JSON, 1 Hz) + log warnings when something breaks:
lidar silent, map not updating, odometry silent, Mega link lost, Pi too hot / low memory."""
import json
import os
import time

try:
    import rclpy
    from nav_msgs.msg import OccupancyGrid, Odometry
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import String
except ImportError:      # logic can be tested without ROS
    rclpy = None
    Node = object


def evaluate(now, last, base_status, pi):
    """last: dict name -> last time a message arrived (or None).  Returns (level, problems)."""
    problems = []

    def silent(name, limit, label, level='error'):
        t = last.get(name)
        if t is None:
            problems.append((level, f'{label}: nothing received yet'))
        elif now - t > limit:
            problems.append((level, f'{label}: silent for {now - t:.0f} s'))

    silent('scan', 2.0, 'lidar /scan')
    silent('odom', 2.0, 'odometry /odom')
    silent('map', 15.0, 'map /map', 'warn')
    if base_status is not None and not base_status.get('connected', True):
        problems.append(('error', 'Arduino Mega link lost (check the USB cable)'))
    if pi.get('temp_c') is not None and pi['temp_c'] > 80.0:
        problems.append(('warn', f'Pi temperature {pi["temp_c"]:.0f} C'))
    if pi.get('mem_free_mb') is not None and pi['mem_free_mb'] < 150.0:
        problems.append(('warn', f'Pi free memory {pi["mem_free_mb"]:.0f} MB'))
    level = 'ok'
    if any(p[0] == 'warn' for p in problems):
        level = 'warn'
    if any(p[0] == 'error' for p in problems):
        level = 'error'
    return level, problems


def read_pi_stats():
    out = dict(temp_c=None, load1=None, mem_free_mb=None)
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            out['temp_c'] = int(f.read().strip()) / 1000.0
    except Exception:  # noqa: BLE001
        pass
    try:
        out['load1'] = os.getloadavg()[0]
    except Exception:  # noqa: BLE001
        pass
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    out['mem_free_mb'] = int(line.split()[1]) / 1024.0
    except Exception:  # noqa: BLE001
        pass
    return out


class HealthNode(Node):
    def __init__(self):
        super().__init__('health')
        self.last = {'scan': None, 'odom': None, 'map': None}
        self.rate = {'scan': 0.0}
        self.base_status = None
        self.state = None
        self.prev_level = 'ok'
        self.prev_msgs = set()
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(Odometry, '/odom', lambda m: self.touch('odom'), 10)
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, '/map', lambda m: self.touch('map'), latched)
        self.create_subscription(String, '/base_status', self.on_base, 10)
        self.create_subscription(String, '/robot_state', self.on_state, 10)
        self.pub = self.create_publisher(String, '/robot_health', 10)
        self.create_timer(1.0, self.tick)
        self.t0 = time.monotonic()

    def now(self):
        return time.monotonic()

    def touch(self, name):
        self.last[name] = self.now()

    def on_scan(self, msg):
        t = self.now()
        prev = self.last['scan']
        if prev is not None and t > prev:
            self.rate['scan'] = 0.8 * self.rate['scan'] + 0.2 / (t - prev)
        self.last['scan'] = t

    def on_base(self, msg):
        try:
            self.base_status = json.loads(msg.data)
        except ValueError:
            pass

    def on_state(self, msg):
        try:
            self.state = json.loads(msg.data)
        except ValueError:
            pass

    def tick(self):
        now = self.now()
        pi = read_pi_stats()
        level, problems = evaluate(now, {k: v for k, v in self.last.items()}, self.base_status, pi)
        if now - self.t0 < 8.0:            # start-up grace period
            level, problems = 'starting', []
        msgs = {f'{lv}: {m}' for lv, m in problems}
        for m in msgs - self.prev_msgs:
            (self.get_logger().error if m.startswith('error') else self.get_logger().warning)(m)
        for m in self.prev_msgs - msgs:
            self.get_logger().info(f'recovered: {m.split(": ", 1)[1]}')
        self.prev_msgs = msgs
        self.prev_level = level
        self.pub.publish(String(data=json.dumps(dict(
            level=level, problems=[m for _, m in problems],
            scan_hz=round(self.rate['scan'], 1), base=self.base_status, pi=pi))))


def main():
    rclpy.init()
    node = HealthNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
