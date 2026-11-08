"""Drives the motors from /cmd_vel and publishes /odom + the odom -> base_link transform.

backend 'serial'  : Arduino Mega on USB (firmware/mega_motor_driver)      <- the real robot
backend 'gpio'    : H-bridge wired directly on the Pi GPIO
backend 'dry_run' : nothing is driven (test on a PC)

Odometry:
  use_encoders:=false (default) -> open loop: computed from what the motors were told to do.
      It drifts (wheel slip); SLAM / AMCL correct it with the lidar. Calibrate the *_scale.
  use_encoders:=true            -> computed from the encoder ticks sent by the Mega.
"""
import json
import time

import rclpy
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster

from . import kinematics as k
from .motors import DryRunMotors, GpioMotors, SerialMotors


class BaseNode(Node):
    def __init__(self):
        super().__init__('base_node')
        d = self.declare_parameter
        d('backend', 'dry_run')                  # 'serial' | 'gpio' | 'dry_run'
        # --- serial (Arduino Mega)
        d('serial_port', '/dev/ttyACM0')
        d('serial_baud', 115200)
        d('serial_boot_wait', 2.0)               # the Mega resets when the port opens
        # --- gpio (only if the H-bridge is wired on the Pi)
        d('driver_type', 'l298n')
        d('left_pins', [17, 27, 18])
        d('right_pins', [22, 23, 19])
        d('pwm_hz', 1000)
        # --- motors
        d('invert_left', False)
        d('invert_right', False)
        d('wheel_separation', 0.1471)            # m, centre to centre
        d('max_wheel_speed', 0.30)               # m/s at 100 % PWM  (calibrate)
        d('min_duty', 0.25)                      # below this the motors stall
        d('max_linear', 0.20)                    # m/s safety clamp
        d('max_angular', 1.5)                    # rad/s safety clamp
        d('max_accel', 0.6)                      # m/s^2
        d('max_ang_accel', 4.0)                  # rad/s^2
        d('cmd_timeout', 0.5)                    # s without a command -> stop
        d('cmd_vel_topic', '/cmd_vel')           # bringup.launch.py sets /cmd_vel_safe (after cmd_mux)
        d('loop_hz', 50.0)
        # --- odometry
        d('linear_scale', 1.0)
        d('angular_scale', 1.0)                  # skid-steer: usually < 1
        d('use_encoders', False)
        d('ticks_per_meter_left', 1000.0)
        d('ticks_per_meter_right', 1000.0)
        d('encoder_invert_left', False)
        d('encoder_invert_right', False)
        d('odom_frame', 'odom')
        d('base_frame', 'base_link')
        d('publish_tf', True)

        self.sep = float(self.p('wheel_separation'))
        self.max_speed = float(self.p('max_wheel_speed'))
        self.min_duty = float(self.p('min_duty'))
        self.use_enc = bool(self.p('use_encoders'))

        backend = str(self.p('backend'))
        if backend == 'serial':
            self.motors = SerialMotors(self.p('serial_port'), self.p('serial_baud'),
                                       self.p('invert_left'), self.p('invert_right'),
                                       self.get_logger(), self.p('serial_boot_wait'))
        elif backend == 'gpio':
            self.motors = GpioMotors(self.p('driver_type'), self.p('left_pins'),
                                     self.p('right_pins'), self.p('pwm_hz'),
                                     self.p('invert_left'), self.p('invert_right'),
                                     self.get_logger())
        elif backend == 'dry_run':
            self.motors = DryRunMotors()
            self.get_logger().warning('backend=dry_run: motors are NOT driven')
        else:
            raise ValueError(f"unknown backend '{backend}' (serial | gpio | dry_run)")
        if self.use_enc and backend != 'serial':
            self.get_logger().warning('use_encoders needs backend:=serial; falling back to open loop')
            self.use_enc = False

        self.cmd_v = self.cmd_w = 0.0      # last requested
        self.cur_v = self.cur_w = 0.0      # after acceleration limit
        self.x = self.y = self.th = 0.0
        self.odo_v = self.odo_w = 0.0
        self.prev_ticks = None
        self.last_stale_warn = 0.0
        self.last_cmd = self.get_clock().now()
        self.last_tick = self.get_clock().now()

        self.create_subscription(Twist, str(self.p('cmd_vel_topic')), self.on_cmd, 10)
        self.status_pub = self.create_publisher(String, '/base_status', 10)
        self.create_timer(0.5, self.publish_status)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.tf_pub = TransformBroadcaster(self)
        self.create_timer(1.0 / float(self.p('loop_hz')), self.tick)
        self.get_logger().info(f'base_node ready (backend={backend}, '
                               f'odometry={"encoders" if self.use_enc else "open loop"})')

    def p(self, name):
        return self.get_parameter(name).value

    def publish_status(self):
        self.status_pub.publish(String(data=json.dumps(dict(
            backend=str(self.p('backend')),
            connected=bool(getattr(self.motors, 'connected', True)),
            odometry='encoders' if self.use_enc else 'open_loop',
            v=round(self.odo_v, 3), w=round(self.odo_w, 3)))))

    def on_cmd(self, msg: Twist):
        self.cmd_v = k.clamp(msg.linear.x, -self.p('max_linear'), self.p('max_linear'))
        self.cmd_w = k.clamp(msg.angular.z, -self.p('max_angular'), self.p('max_angular'))
        self.last_cmd = self.get_clock().now()

    def tick(self):
        now = self.get_clock().now()
        dt = (now - self.last_tick).nanoseconds * 1e-9
        self.last_tick = now
        if dt <= 0.0 or dt > 0.5:
            return

        if (now - self.last_cmd).nanoseconds * 1e-9 > self.p('cmd_timeout'):
            self.cmd_v = self.cmd_w = 0.0

        # acceleration limits (protect the supply and the gears)
        self.cur_v = k.slew(self.cur_v, self.cmd_v, self.p('max_accel') * dt)
        self.cur_w = k.slew(self.cur_w, self.cmd_w, self.p('max_ang_accel') * dt)

        # body -> sides -> duty -> motors
        vl, vr = k.wheel_speeds(self.cur_v, self.cur_w, self.sep)
        dl = k.speed_to_duty(vl, self.max_speed, self.min_duty)
        dr = k.speed_to_duty(vr, self.max_speed, self.min_duty)
        self.motors.set(dl, dr)

        if self.use_enc:
            self.update_from_encoders()
        else:   # open loop: assume the (acceleration-limited) command is achieved
            v, w = k.body_velocity(vl if dl != 0.0 else 0.0, vr if dr != 0.0 else 0.0,
                                   self.sep, self.p('linear_scale'), self.p('angular_scale'))
            self.x, self.y, self.th = k.integrate(self.x, self.y, self.th, v, w, dt)
            self.odo_v, self.odo_w = v, w
        self.publish(now.to_msg())

    def update_from_encoders(self):
        tk = self.motors.ticks()
        if tk is None or time.monotonic() - tk[2] > 0.5:
            self.odo_v = self.odo_w = 0.0
            if time.monotonic() - self.last_stale_warn > 5.0:
                self.last_stale_warn = time.monotonic()
                self.get_logger().warning('no encoder data from the Mega '
                                       '(is ENCODERS 1 in the firmware?)')
            return
        if self.prev_ticks is None:
            self.prev_ticks = tk
            return
        if tk[2] == self.prev_ticks[2]:
            return                                   # no new packet since the last tick
        dt_e = tk[2] - self.prev_ticks[2]
        sl = -1 if self.p('encoder_invert_left') else 1
        sr = -1 if self.p('encoder_invert_right') else 1
        dtl = sl * (tk[0] - self.prev_ticks[0])
        dtr = sr * (tk[1] - self.prev_ticks[1])
        self.prev_ticks = tk
        if not 0.0 < dt_e < 0.5:
            return
        dist, dth = k.ticks_to_motion(dtl, dtr, self.p('ticks_per_meter_left'),
                                      self.p('ticks_per_meter_right'), self.sep,
                                      self.p('linear_scale'), self.p('angular_scale'))
        self.x, self.y, self.th = k.integrate_delta(self.x, self.y, self.th, dist, dth)
        self.odo_v, self.odo_w = dist / dt_e, dth / dt_e

    def publish(self, stamp):
        _, _, qz, qw = k.yaw_to_quaternion(self.th)
        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = self.p('odom_frame')
        odom.child_frame_id = self.p('base_frame')
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x = self.odo_v
        odom.twist.twist.angular.z = self.odo_w
        s_xy, s_th = (0.01, 0.05) if self.use_enc else (0.05, 0.2)
        cov = [0.0] * 36
        for i, val in ((0, s_xy), (7, s_xy), (14, 1e3), (21, 1e3), (28, 1e3), (35, s_th)):
            cov[i] = val
        odom.pose.covariance = cov
        odom.twist.covariance = cov
        self.odom_pub.publish(odom)

        if self.p('publish_tf'):
            t = TransformStamped()
            t.header.stamp = stamp
            t.header.frame_id = self.p('odom_frame')
            t.child_frame_id = self.p('base_frame')
            t.transform.translation.x = self.x
            t.transform.translation.y = self.y
            t.transform.rotation.z = qz
            t.transform.rotation.w = qw
            self.tf_pub.sendTransform(t)

    def destroy_node(self):
        try:
            if hasattr(self.motors, 'close'):
                self.motors.close()
            else:
                self.motors.stop()
        except Exception:  # noqa: BLE001
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = BaseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
