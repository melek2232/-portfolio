#!/usr/bin/env python3
"""Smoke test of robot_base/base_node.py WITHOUT ROS: rclpy and the message types are replaced
by tiny stand-ins and the clock is faked. Checks the control loop, limits, open-loop odometry,
encoder odometry, timeout and the serial backend wiring.   Usage: python3 test_base_node_smoke.py
"""
import math
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))


class Obj:
    """Accepts any attribute: msg.pose.pose.position.x = 1 just works."""
    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        o = Obj()
        object.__setattr__(self, name, o)
        return o


class Dur:
    def __init__(self, ns): self.nanoseconds = ns


class Time:
    def __init__(self, ns): self.nanoseconds = ns
    def __sub__(self, other): return Dur(self.nanoseconds - other.nanoseconds)
    def to_msg(self): return None


class Clock:
    ns = 0
    def now(self): return Time(Clock.ns)


class Logger:
    msgs = []
    def info(self, m): self.msgs.append(('info', m))
    def warn(self, m): self.msgs.append(('warn', m))
    warning = warn
    def error(self, m): self.msgs.append(('error', m))


class Publisher:
    def __init__(self): self.sent = []
    def publish(self, m): self.sent.append(m)


PRESET = {}


class FakeNode:
    def __init__(self, name):
        self.params, self.timers, self.subs, self.pubs = {}, [], {}, {}
    def declare_parameter(self, name, value): self.params[name] = PRESET.get(name, value)
    def get_parameter(self, name): return types.SimpleNamespace(value=self.params[name])
    def get_logger(self): return Logger()
    def get_clock(self): return Clock()
    def create_subscription(self, typ, topic, cb, qos): self.subs[topic] = cb
    def create_publisher(self, typ, topic, qos):
        self.pubs[topic] = Publisher(); return self.pubs[topic]
    def create_timer(self, period, cb): self.timers.append(cb)
    def destroy_node(self): pass


# ---- install the stand-ins before importing the node
def mod(name, **attrs):
    m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m; return m

mod('rclpy', init=lambda: None, spin=lambda n: None, try_shutdown=lambda: None)
mod('rclpy.node', Node=FakeNode)
mod('geometry_msgs'); mod('geometry_msgs.msg', Twist=Obj, TransformStamped=Obj)
mod('nav_msgs'); mod('nav_msgs.msg', Odometry=Obj)
class StrMsg:
    def __init__(self, data=''): self.data = data
mod('std_msgs'); mod('std_msgs.msg', String=StrMsg)
class TFB:
    def __init__(self, node): self.sent = []
    def sendTransform(self, t): self.sent.append(t)
mod('tf2_ros', TransformBroadcaster=TFB)

from robot_base import base_node  # noqa: E402
from robot_base.motors import Motors  # noqa: E402

fails = 0


def check(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info and not cond else ''))
    fails += 0 if cond else 1


class Recorder(Motors):
    def __init__(self): self.calls = []; self.tk = None
    def set(self, l, r): self.calls.append((l, r))
    def ticks(self): return self.tk


def make(**params):
    PRESET.clear(); PRESET.update(params)
    return base_node.BaseNode()


def drive(node, v, w, seconds, hz=50.0):
    Clock.ns += 0
    dt = 1.0 / hz
    for i in range(int(seconds * hz)):
        Clock.ns += int(dt * 1e9)
        if i % 5 == 0:
            msg = Obj(); msg.linear.x = v; msg.angular.z = w
            node.subs['/cmd_vel'](msg)
        node.tick()


# ---------- open loop, dry run
Clock.ns = 10**9
n = make()
n.motors = Recorder()
n.tick()                                   # first tick only sets the time base
drive(n, 0.10, 0.0, 3.0)
check('open loop: drives about 0.3 m in 3 s', 0.25 < n.x < 0.31, f'x={n.x:.3f}')
check('open loop: stays on the x axis', abs(n.y) < 1e-6 and abs(n.th) < 1e-6)
check('odom + tf published', len(n.odom_pub.sent) > 100 and len(n.tf_pub.sent) > 100)
l, r = n.motors.calls[-1]
check('equal duty on both sides when going straight', abs(l - r) < 1e-9 and 0.45 < l < 0.55, f'{l},{r}')

drive(n, 0.0, 0.0, 1.0)
check('stops when the command is zero', n.motors.calls[-1] == (0.0, 0.0))

n.th = 0.0
drive(n, 0.0, 0.5, 2.0)
check('turn in place: positive w turns counter-clockwise', 0.8 < n.th < 1.1, f'th={n.th:.3f}')
l, r = n.motors.calls[-1]
check('turning left: left side backward, right side forward', l < 0 < r, f'{l},{r}')

msg = Obj(); msg.linear.x = 0.15; msg.angular.z = 0.0
n.subs['/cmd_vel'](msg)
for _ in range(35):                        # then no /cmd_vel for 0.7 s > cmd_timeout
    Clock.ns += int(0.02e9)
    n.tick()
check('cmd_timeout stops the robot', n.cmd_v == 0.0 and n.cmd_w == 0.0)

msg = Obj(); msg.linear.x = 5.0; msg.angular.z = -9.0
n.subs['/cmd_vel'](msg)
check('commands are clamped to max_linear / max_angular',
      n.cmd_v == n.params['max_linear'] and n.cmd_w == -n.params['max_angular'])

# ---------- encoder odometry
Clock.ns = 10**9
n = make()
n.use_enc = True
n.motors = Recorder()
n.params['ticks_per_meter_left'] = 1000.0
n.params['ticks_per_meter_right'] = 1000.0
import time
cnt = [0, 0]
def fake_ticks():
    cnt[0] += 10; cnt[1] += 10
    return (cnt[0], cnt[1], time.monotonic())
n.motors.ticks = fake_ticks
n.tick()
for _ in range(100):
    Clock.ns += int(0.02e9); time.sleep(0.001); n.tick()
check('encoders: 10 ticks per step -> 1 cm per step', 0.5 < n.x < 1.1, f'x={n.x:.3f}')
n.prev_ticks = None; x0 = n.x
cnt[:] = [0, 0]
def turn_ticks():
    cnt[0] -= 10; cnt[1] += 10
    return (cnt[0], cnt[1], time.monotonic())
n.motors.ticks = turn_ticks
n.tick()
n.th = 0.0
for _ in range(20):
    Clock.ns += int(0.02e9); time.sleep(0.001); n.tick()
check('encoders: opposite ticks turn on the spot', n.th > 2.0 and abs(n.x - x0) < 0.05,
      f'th={n.th:.2f} dx={n.x - x0:.3f}')
n.params['encoder_invert_left'] = True
n.params['encoder_invert_right'] = True
n.prev_ticks = None; cnt[:] = [0, 0]; n.th = 0.0
n.tick()
for _ in range(20):
    Clock.ns += int(0.02e9); time.sleep(0.001); n.tick()
check('encoder_invert flips the direction', n.th < -2.0, f'th={n.th:.2f}')

n.motors.ticks = lambda: None
n.tick()
check('no encoder data -> velocity 0, no crash', n.odo_v == 0.0)

# ---------- odom:=lidar (robot.launch.py): rf2o owns /odom + TF, base_node only drives the motors
from robot_base import odom_select  # noqa: E402
Clock.ns = 10**9
n = make(**odom_select.base_node_params('lidar'))
n.motors = Recorder()
n.tick()
drive(n, 0.10, 0.0, 1.0)
check('lidar mode: wheel estimate on /odom_wheels, nothing on /odom',
      '/odom' not in n.pubs and len(n.pubs['/odom_wheels'].sent) > 30)
check('lidar mode: no odom -> base_link TF from base_node', len(n.tf_pub.sent) == 0)
check('lidar mode: motors still driven', n.motors.calls[-1][0] > 0.3)
n.publish_status()
check("lidar mode: /base_status says odometry 'lidar'",
      '"odometry": "lidar"' in n.status_pub.sent[-1].data, n.status_pub.sent[-1].data)
n = make(**odom_select.base_node_params('wheels'))
check('wheels mode: /odom + TF as before', '/odom' in n.pubs and n.params['publish_tf'] is True)

# ---------- unknown backend
try:
    make(backend='banana')
    check('unknown backend raises', False)
except ValueError:
    check('unknown backend raises', True)

print('ALL PASSED' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
