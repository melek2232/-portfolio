"""Explorer logic with the lidar mounted rotated by 180 deg gives the same commands (no ROS needed)."""
import math, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from robot_base.explore import Wanderer

def room_scan(n=360):
    """Robot facing +x in a 4 m x 3 m box, wall 0.4 m ahead on the right side only."""
    out = []
    for i in range(n):
        a = -math.pi + i * 2 * math.pi / n
        d = 9.0
        for wall in ((1.5 / math.cos(a)) if math.cos(a) > 1e-6 else 9, (-1.5 / math.cos(a)) if math.cos(a) < -1e-6 else 9,
                     (1.0 / math.sin(a)) if math.sin(a) > 1e-6 else 9, (-1.0 / math.sin(a)) if math.sin(a) < -1e-6 else 9):
            d = min(d, wall)
        out.append(d)
    return out

for scene, ranges in (('open', room_scan()),):
    inc = 2 * math.pi / 360
    a = Wanderer(rng=random.Random(1)); b = Wanderer(rng=random.Random(1))
    n = len(ranges); half = n // 2
    rotated = ranges[half:] + ranges[:half]          # lidar turned 180 deg: beam 0 now looks backwards
    for t in range(200):
        ra = a.step(ranges, -math.pi, inc, 0.12, 8.0, t * 0.1)
        rb = b.step(rotated, -math.pi + math.pi, inc, 0.12, 8.0, t * 0.1)   # a_min + lidar_yaw
        assert ra == rb, (t, ra, rb)
print('PASS explorer gives identical commands with lidar_yaw = pi')
# wall right in front -> must stop / turn, never drive into it
w = Wanderer(rng=random.Random(2)); r = [9.0] * 360
for i in range(360):
    ang = -math.pi + i * inc
    if abs(ang) < 0.5: r[i] = 0.2 / max(math.cos(ang), 0.1)
v, om = w.step(r, -math.pi, inc, 0.12, 8.0, 0.0)
assert v <= 0.0, v
print('PASS no forward motion with a wall 0.2 m ahead')
