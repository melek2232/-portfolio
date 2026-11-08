#!/usr/bin/env python3
"""Mux + safety layer + explorer driving a SIMULATED robot in the simulated room (no ROS).
1. Teleop pushes straight into walls for 60 s: the safety layer must stop it, 0 collisions.
2. Explorer through the mux for 150 s: 0 collisions, and it keeps moving."""
import math, os, random, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'robot_description', 'tools'))
import offline_check as oc
from robot_base.mux import Mux, corridor_clearance
from robot_base.scan_filter import filter_ranges
from robot_base.explore import Wanderer

occ, _ = oc.build_world()
INC = 2 * math.pi / oc.BEAMS

def run(mode, seconds, seed=1, cmd=None, noise=0.01):
    rng_noise = np.random.default_rng(seed)
    mux = Mux(initial_mode=mode)
    wander = Wanderer(rng=random.Random(seed), v=0.15)
    x = y = yaw = 0.0
    dt, t = 0.1, 0.0
    collisions, path, min_front = 0, 0.0, 9.9
    while t < seconds:
        lx = x + math.cos(yaw) * oc.LIDAR_X
        ly = y + math.sin(yaw) * oc.LIDAR_X
        ranges, _ = oc.scan(occ, lx, ly, yaw)
        ranges = ranges + rng_noise.normal(0, noise, ranges.shape)
        ranges = np.where(np.isfinite(ranges) & (ranges >= oc.R_MIN) & (ranges <= oc.R_MAX), ranges, np.inf)
        filt = filter_ranges(ranges.tolist(), INC, 0.12, 8.0)
        f, r = corridor_clearance(filt, -math.pi, INC, 0.12, 8.0, 0.205, 0.081, 0.075, 0.05)
        mux.on_clearance(f, r, t)
        if mode == 'explore':
            v, w = wander.step(filt, -math.pi, INC, 0.12, 8.0, t)
            mux.on_cmd('explore', v, w, t)
        else:
            mux.on_cmd('manual', *cmd, t)
        v, w, info = mux.step(t)
        ny, nx, nyaw = y + v * math.sin(yaw) * dt, x + v * math.cos(yaw) * dt, yaw + w * dt
        if oc.body_collides(occ, nx, ny, nyaw):
            collisions += 1
        else:
            path += math.hypot(nx - x, ny - y)
            x, y, yaw = nx, ny, nyaw
        min_front = min(min_front, f)
        t += dt
    return collisions, path, min_front

fails = 0
def check(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{info}]' if (info and not cond) else ''))
    fails += 0 if cond else 1

c, p, mf = run('manual', 60, cmd=(0.2, 0.0))
check(f'teleop straight into the wall: collisions={c}, travelled {p:.1f} m, closest {mf:.2f} m', c == 0 and p > 1.0 and mf >= 0.05, (c, p, mf))
c, p, mf = run('manual', 60, cmd=(0.2, 0.3))
check(f'teleop arc into walls: collisions={c}', c == 0, c)
for seed in (1, 2, 3):
    c, p, mf = run('explore', 150, seed=seed)
    check(f'explorer through the mux, seed {seed}: collisions={c}, path={p:.1f} m', c == 0 and p > 5, (c, p))
print('ALL PASSED' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
