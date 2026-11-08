"""fake_robot.py with ROS replaced by stand-ins, run from an 'installed' layout (files copied flat)."""
import math, os, shutil, sys, tempfile, types
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lib = tempfile.mkdtemp(); share = tempfile.mkdtemp()
for f in ['scripts/fake_robot.py', 'scripts/wander.py', 'tools/offline_check.py', 'tools/make_truth_map.py']:
    shutil.copy(os.path.join(PKG, f), lib)
shutil.copytree(os.path.join(PKG, 'worlds'), os.path.join(share, 'worlds'))

class Msg:
    def __init__(self, **k): self.__dict__.update(k)
    def __getattr__(self, n):
        if n.startswith('__'): raise AttributeError(n)
        o = Msg(); object.__setattr__(self, n, o); return o
def mod(name, **attrs):
    m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m; return m
sent = []
class Pub:
    def __init__(s, t): s.t = t
    def publish(s, m): sent.append((s.t, m))
class Node:
    def __init__(s, name): s.p = {}
    def declare_parameter(s, k, v): s.p[k] = v
    def get_parameter(s, k): return Msg(value=s.p[k])
    def create_publisher(s, T, t, q): return Pub(t)
    def create_subscription(*a): pass
    def create_timer(s, dt, cb): s.cb = cb
    def get_logger(s): return Msg(info=lambda *a: None)
    def get_clock(s): return Msg(now=lambda: Msg(to_msg=lambda: 0))
class TB:
    def __init__(s, n): pass
    def sendTransform(s, t): sent.append(('tf', t))
mod('rclpy'); mod('rclpy.node', Node=Node); mod('rclpy.qos', qos_profile_sensor_data=1)
mod('ament_index_python'); mod('ament_index_python.packages', get_package_share_directory=lambda n: share)
mod('geometry_msgs'); mod('geometry_msgs.msg', TransformStamped=Msg, Twist=Msg)
mod('nav_msgs'); mod('nav_msgs.msg', Odometry=Msg)
mod('sensor_msgs'); mod('sensor_msgs.msg', JointState=Msg, LaserScan=Msg)
mod('tf2_ros', TransformBroadcaster=TB)
sys.path.insert(0, lib)
import fake_robot
n = fake_robot.FakeRobot()
for _ in range(1200): n.cb()                      # 120 s
scans = [m for t, m in sent if t == '/scan']; odoms = [m for t, m in sent if t == '/odom']
assert len(scans) == 1200 and len(odoms) == 1200
s = scans[-1]
assert s.header.frame_id == 'lidar_link' and len(s.ranges) == 360
fin = sum(math.isfinite(r) for r in s.ranges); assert fin > 50, fin
xs = [o.pose.pose.position.x for o in odoms]; ys = [o.pose.pose.position.y for o in odoms]
dist = sum(math.hypot(xs[i+1]-xs[i], ys[i+1]-ys[i]) for i in range(len(xs)-1))
assert dist > 5, dist
assert max(map(abs, xs)) < 4.2 and max(map(abs, ys)) < 4.2     # stays inside the room
print(f'PASS fake_robot: 120 s, {dist:.1f} m driven, {fin}/360 valid beams, stays in the room')
