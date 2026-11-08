#!/usr/bin/env python3
"""Offline tests: command arbitration + safety layer (mux.py), scan filter, health logic, autosave pruning."""
import math, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from robot_base.mux import Mux, corridor_clearance, speed_scale, INF
from robot_base.scan_filter import filter_ranges
from robot_base.health import evaluate

fails = 0
def check(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{info}]' if (info and not cond) else ''))
    fails += 0 if cond else 1

INC = 2 * math.pi / 360
def scan(fn):
    return [fn(-math.pi + i * INC) for i in range(360)]
FREE = scan(lambda a: 6.0)

def with_wall_ahead(dist_from_lidar):
    return scan(lambda a: (dist_from_lidar / max(math.cos(a), 1e-3)) if abs(a) < 0.6 else 6.0)

# ---- clearance
f, r = corridor_clearance(FREE, -math.pi, INC, 0.12, 8.0, 0.205, 0.081, 0.075, 0.05)
check('free room: infinite clearance? (walls only far)', f > 5 and r > 5, (f, r))
f, r = corridor_clearance(with_wall_ahead(0.40), -math.pi, INC, 0.12, 8.0, 0.205, 0.081, 0.075, 0.05)
check('wall 0.40 m from lidar -> 0.195 m free ahead', abs(f - 0.195) < 0.03, f)
# lidar mounted backwards (yaw = pi): a wall behind the lidar is ahead of the robot
back_wall = scan(lambda a: (0.40 / max(-math.cos(a), 1e-3)) if abs(abs(a) - math.pi) < 0.6 else 6.0)
f, r = corridor_clearance(back_wall, -math.pi + math.pi, INC, 0.12, 8.0, 0.205, 0.081, 0.075, 0.05)
check('lidar_yaw=pi puts that wall ahead', f < 0.3, f)
one = list(FREE); one[180] = 0.3          # a single noisy point dead ahead
f1, _ = corridor_clearance(one, -math.pi, INC, 0.12, 8.0, 0.205, 0.081, 0.075, 0.05)
check('one noisy point is ignored', f1 > 1.0, f1)
check('speed_scale ramps', speed_scale(0.05, .1, .45) == 0 and speed_scale(1, .1, .45) == 1
      and abs(speed_scale(0.275, .1, .45) - 0.5) < 1e-9)

# ---- mux
m = Mux(initial_mode='manual')
t = 100.0
m.on_clearance(INF, INF, t)
m.on_cmd('manual', 0.15, 0.3, t)
v, w, i = m.step(t + 0.1)
check('manual command passes', (v, w) == (0.15, 0.3) and i['reason'] == 'ok', (v, w, i))
v, w, i = m.step(t + 0.7)
check('source timeout stops (dead-man)', (v, w) == (0, 0) and i['reason'] == 'no_command', i)
m.on_cmd('explore', 0.1, 0, t + 0.7)
v, w, i = m.step(t + 0.8)
check('explore command ignored in manual mode', v == 0, (v, w, i))
check('mode switch accepted', m.set_mode('explore'))
m.on_cmd('explore', 0.1, 0.0, t + 0.9)
v, w, i = m.step(t + 1.0)
check('explore command used in explore mode', v == 0.1, (v, w, i))
m.on_cmd('manual', 0.15, 0, t + 1.0)
v, w, i = m.step(t + 1.0)
check('teleop ignored in explore mode', v == 0.1)
check('unknown mode refused', not m.set_mode('turbo') and m.mode == 'explore')
m.set_mode('manual')
m.on_clearance(0.05, INF, t + 1.0)
m.on_cmd('manual', 0.2, 0.0, t + 1.1)
v, w, i = m.step(t + 1.1)
check('obstacle at stop distance blocks forward', v == 0 and i['reason'] == 'obstacle', (v, i))
m.on_cmd('manual', 0.0, 1.0, t + 1.1)
v, w, i = m.step(t + 1.1)
check('turning in place still allowed', w == 1.0, (v, w))
m.on_cmd('manual', -0.15, 0.0, t + 1.1)
v, w, i = m.step(t + 1.1)
check('reverse allowed when the rear is free', v == -0.15, (v, w, i))
m.on_clearance(0.275, INF, t + 1.2)
m.on_cmd('manual', 0.2, 0.0, t + 1.2)
v, w, i = m.step(t + 1.2)
check('slows down between stop and slow distance', 0.05 < v < 0.15, v)
m.on_clearance(INF, INF, t + 1.3)
m.on_cmd('manual', 1.0, 9.0, t + 1.3)
v, w, i = m.step(t + 1.3)
check('speeds are clamped', v == 0.20 and w == 1.2, (v, w))
v, w, i = m.step(t + 3.0)
check('lidar silent -> blocked', i['reason'] in ('blind', 'no_command'))
m.on_cmd('manual', 0.1, 0.0, t + 3.0)
v, w, i = m.step(t + 3.0)
check('blind robot does not move', v == 0 and i['reason'] == 'blind', i)
m2 = Mux(initial_mode='manual', block_when_blind=False)
m2.on_cmd('manual', 0.1, 0.0, 5.0)
check('block_when_blind can be disabled', m2.step(5.0)[0] == 0.1)
# e-stop
m.on_clearance(INF, INF, t + 3.1)
m.on_cmd('manual', 0.1, 0.0, t + 3.1)
m.set_estop(True)
v, w, i = m.step(t + 3.1)
check('e-stop zeroes the output and sets mode stop', v == 0 and i['reason'] == 'estop' and m.mode == 'stop')
check('mode change refused while e-stopped', not m.set_mode('manual'))
m.set_estop(False)
m.on_cmd('manual', 0.1, 0.0, t + 3.2); m.on_clearance(INF, INF, t + 3.2)
check('after release the robot stays stopped until a mode is chosen', m.step(t + 3.2)[0] == 0 and m.mode == 'stop')
check('then a mode can be chosen again', m.set_mode('manual'))

# ---- scan filter
rng = [2.0] * 100
rng[50] = 3.5                           # isolated speckle
rng[10] = 0.0; rng[11] = float('nan'); rng[12] = 20.0
out = filter_ranges(rng, INC, 0.12, 8.0)
check('speckle removed', math.isinf(out[50]))
check('invalid beams -> inf', all(math.isinf(out[k]) for k in (10, 11, 12)))
check('wall points kept', out[30] == 2.0 and out[70] == 2.0)
edge = [2.0] * 60 + [float('inf')] * 40
check('wall edge points kept', filter_ranges(edge, INC, 0.12, 8.0)[59] == 2.0)
step = [2.0] * 50 + [4.0] * 50
o = filter_ranges(step, INC, 0.12, 8.0)
check('depth step (corner) keeps both sides', o[49] == 2.0 and o[50] == 4.0)

# ---- health
now = 100.0
lvl, pr = evaluate(now, {'scan': 99.5, 'odom': 99.5, 'map': 95.0}, {'connected': True}, {'temp_c': 50, 'mem_free_mb': 900})
check('health ok', lvl == 'ok' and not pr, pr)
lvl, pr = evaluate(now, {'scan': 90.0, 'odom': 99.5, 'map': 95.0}, {'connected': True}, {})
check('lidar silent -> error', lvl == 'error' and any('lidar' in m for _, m in pr), pr)
lvl, pr = evaluate(now, {'scan': 99.5, 'odom': 99.5, 'map': 50.0}, {'connected': False}, {})
check('Mega lost -> error, old map -> warn', lvl == 'error' and len(pr) == 2, pr)
lvl, pr = evaluate(now, {'scan': 99.5, 'odom': 99.5, 'map': 99.0}, None, {'temp_c': 85.0})
check('hot Pi -> warn', lvl == 'warn', pr)

# ---- autosave pruning (pure part)
sys.modules.setdefault('rclpy', type(sys)('rclpy'))
for name in ('rclpy.node', 'nav_msgs', 'nav_msgs.msg', 'rclpy.qos'):
    sys.modules.setdefault(name, type(sys)(name))
sys.modules['rclpy.node'].Node = object
sys.modules['nav_msgs.msg'].OccupancyGrid = object
q = sys.modules['rclpy.qos']; q.DurabilityPolicy = q.QoSProfile = q.ReliabilityPolicy = object
from robot_base.map_autosave import prune
d = tempfile.mkdtemp()
for k in range(5):
    for ext in ('.yaml', '.pgm'):
        open(os.path.join(d, f'map_2026010{k}_000000{ext}'), 'w').close()
open(os.path.join(d, 'latest.yaml'), 'w').close()
prune(d, 2)
left = sorted(os.listdir(d))
check('autosave keeps the 2 newest + latest', left == ['latest.yaml', 'map_20260103_000000.pgm',
      'map_20260103_000000.yaml', 'map_20260104_000000.pgm', 'map_20260104_000000.yaml'], left)

print('ALL PASSED' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
