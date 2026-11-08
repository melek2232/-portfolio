#!/usr/bin/env python3
"""Self-driving explorer: drives around and avoids obstacles so SLAM can build the map.

Reactive only (no map needed): drive forward, turn away from walls, back up when stuck,
and make a random turn every 10-25 s so the robot visits the whole room.
The robot drives toward +x of base_link; the lidar frame has the same orientation.
"""
import math
import random

try:
    import rclpy
    from geometry_msgs.msg import Twist
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan
except ImportError:          # lets the logic be tested without ROS
    rclpy = None
    Node = object

# Footprint relative to the lidar (the lidar is 0.068 m behind base_link's centre)
FRONT = 0.205        # distance lidar -> front of the body
REAR = 0.081         # distance lidar -> rear of the body
HALF_W = 0.075       # half width of the body
PIVOT_X = 0.068      # base_link centre, seen from the lidar (turning centre)
PIVOT_R = 0.19       # radius swept when turning in place


class Wanderer:
    """Pure logic: step(scan) -> (linear, angular)."""

    def __init__(self, rng=None, v=0.15, w=0.7):
        self.rng = rng or random.Random()
        self.v_max = v
        self.w_turn = w
        self.state = 'drive'
        self.state_t = 0.0
        self.turn_dir = 1.0
        self.turn_until = None       # set for random turns (timed), None = until clear
        self.next_perturb = None

    # ---- scan analysis -------------------------------------------------
    @staticmethod
    def analyse(ranges, a_min, a_inc, r_min, r_max):
        fwd = rear = left = right = 9.9
        blocked = False
        left_sum = right_sum = 0.0
        left_n = right_n = 0
        cap = 2.5
        for i, r in enumerate(ranges):
            if r != r or r < r_min:                   # NaN or below range: ignore
                continue
            if r == float('inf') or r > r_max:
                r = r_max
            a = a_min + i * a_inc
            ca, sa = math.cos(a), math.sin(a)
            x, y = r * ca, r * sa
            if abs(y) < HALF_W + 0.06:
                if x > 0.0:
                    fwd = min(fwd, x - FRONT)
                else:
                    rear = min(rear, -x - REAR)
            if abs(x) < 0.15:
                if y > 0.0:
                    left = min(left, y - HALF_W)
                else:
                    right = min(right, -y - HALF_W)
            if math.hypot(x - PIVOT_X, y) < PIVOT_R:
                blocked = True
            deg = math.degrees(math.atan2(sa, ca))     # wrapped to -180..180 (lidar may be mounted rotated)
            if 10.0 <= deg <= 100.0:
                left_sum += min(r, cap)
                left_n += 1
            elif -100.0 <= deg <= -10.0:
                right_sum += min(r, cap)
                right_n += 1
        left_score = left_sum / left_n if left_n else 0.0
        right_score = right_sum / right_n if right_n else 0.0
        return fwd, rear, left, right, left_score, right_score, blocked

    # ---- behaviour -----------------------------------------------------
    def _set(self, state, now):
        self.state = state
        self.state_t = now

    def step(self, ranges, a_min, a_inc, r_min, r_max, now):
        fwd, rear, left, right, ls, rs, blocked = self.analyse(
            ranges, a_min, a_inc, r_min, r_max)
        if self.next_perturb is None:
            self.next_perturb = now + self.rng.uniform(10.0, 25.0)

        if self.state == 'drive':
            if fwd < 0.25 or blocked:
                if (fwd < 0.10 or blocked) and rear > 0.25:
                    self._set('back', now)
                else:
                    self.turn_dir = 1.0 if ls >= rs else -1.0
                    self.turn_until = None
                    self._set('turn', now)
                return 0.0, 0.0
            if now >= self.next_perturb:
                self.turn_dir = self.rng.choice((-1.0, 1.0))
                angle = math.radians(self.rng.uniform(40.0, 150.0))
                self.turn_until = now + angle / self.w_turn
                self.next_perturb = now + self.rng.uniform(10.0, 25.0)
                self._set('turn', now)
                return 0.0, 0.0
            v = self.v_max if fwd > 0.6 else max(0.06, self.v_max * (fwd - 0.1) / 0.5)
            w = 0.0
            if left < 0.10:
                w -= 0.5
            if right < 0.10:
                w += 0.5
            return v, w

        if self.state == 'back':
            if now - self.state_t > 1.2 or rear < 0.15:
                self.turn_dir = 1.0 if ls >= rs else -1.0
                self.turn_until = None
                self._set('turn', now)
                return 0.0, 0.0
            return -0.08, 0.0

        # turn in place
        t = now - self.state_t
        if self.turn_until is not None:
            done = now >= self.turn_until
        else:
            done = (fwd > 0.7 and t > 0.5) or t > 8.0
        if done:
            self._set('drive', now)
            return 0.0, 0.0
        if blocked and rear > 0.25 and t > 1.0:
            self._set('back', now)
            return 0.0, 0.0
        return 0.0, self.turn_dir * self.w_turn


class WanderNode(Node):
    def __init__(self):
        super().__init__('wander')
        self.declare_parameter('start_delay', 6.0)
        self.declare_parameter('max_speed', 0.15)
        self.declare_parameter('turn_speed', 0.7)
        self.logic = Wanderer(v=float(self.get_parameter('max_speed').value),
                              w=float(self.get_parameter('turn_speed').value))
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        self.scan = None
        self.first_scan_t = None
        self.create_timer(0.1, self.tick)
        self.get_logger().info('wander: waiting for /scan ...')

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_scan(self, msg):
        self.scan = msg
        self.scan_t = self.now()
        if self.first_scan_t is None:
            self.first_scan_t = self.scan_t
            self.get_logger().info('wander: scan received, starting soon')

    def tick(self):
        cmd = Twist()
        now = self.now()
        if (self.scan is None or now - self.first_scan_t < float(self.get_parameter('start_delay').value)
                or now - self.scan_t > 1.0):
            self.pub.publish(cmd)
            return
        m = self.scan
        v, w = self.logic.step(m.ranges, m.angle_min, m.angle_increment,
                               max(m.range_min, 0.05), m.range_max, now)
        cmd.linear.x = float(v)
        cmd.angular.z = float(w)
        self.pub.publish(cmd)

    def stop(self):
        try:
            self.pub.publish(Twist())
        except Exception:  # noqa: BLE001
            pass


def main():
    rclpy.init()
    node = WanderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
