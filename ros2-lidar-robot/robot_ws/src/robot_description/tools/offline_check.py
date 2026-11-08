#!/usr/bin/env python3
"""Offline check of scripts/wander.py: ray-cast lidar in the ideal map, unicycle robot.

No ROS and no Gazebo needed.  It reports collisions and how much of the room the lidar saw.
Also writes maps/offline_preview.png: a map built from the lidar with PERFECT poses
(a preview of the goal, not a Gazebo/SLAM result).
Usage: python3 tools/offline_check.py [seconds] [seed]
"""
import importlib.util
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_truth_map as tm  # noqa: E402

_w = os.path.join(PKG, 'scripts', 'wander.py')
if not os.path.exists(_w):                 # installed layout: wander.py sits next to this file
    _w = os.path.join(HERE, 'wander.py')
WORLD = os.path.join(PKG, 'worlds', 'mapping_room.sdf')   # fake_robot.py overrides this
spec = importlib.util.spec_from_file_location('wander', _w)
wander = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wander)

RES, HALF = tm.RES, tm.HALF
N = int(2 * HALF / RES)
LIDAR_X = -0.068                     # lidar position in base_link
BODY = (-0.149, 0.137, -0.075, 0.075)  # xmin, xmax, ymin, ymax in base_link
R_MAX, R_MIN, BEAMS = 10.0, 0.12, 360


def build_world():
    shapes = tm.load_shapes(WORLD)
    xs = -HALF + (np.arange(N) + 0.5) * RES
    occ = tm.occupied_mask(shapes, xs, xs)       # [iy, ix]
    X, Y = np.meshgrid(xs, xs)
    inside = (np.abs(X) < 3.9) & (np.abs(Y) < 3.9) & ~occ
    return occ, inside


def cell(x, y):
    return (np.clip(((y + HALF) / RES).astype(int), 0, N - 1),
            np.clip(((x + HALF) / RES).astype(int), 0, N - 1))


def scan(occ, px, py, yaw):
    ang = yaw + (-math.pi + np.arange(BEAMS) * (2 * math.pi / BEAMS))
    steps = np.arange(R_MIN, R_MAX, 0.03)
    xs = px + np.outer(np.cos(ang), steps)
    ys = py + np.outer(np.sin(ang), steps)
    iy, ix = cell(xs, ys)
    hit = occ[iy, ix]
    first = np.where(hit.any(axis=1), hit.argmax(axis=1), -1)
    rng = np.where(first >= 0, steps[np.clip(first, 0, None)], float('inf'))
    return rng, ang


def body_collides(occ, bx, by, yaw):
    pts = []
    for x in np.linspace(BODY[0], BODY[1], 12):
        pts += [(x, BODY[2]), (x, BODY[3])]
    for y in np.linspace(BODY[2], BODY[3], 6):
        pts += [(BODY[0], y), (BODY[1], y)]
    p = np.array(pts)
    c, s = math.cos(yaw), math.sin(yaw)
    wx = bx + c * p[:, 0] - s * p[:, 1]
    wy = by + s * p[:, 0] + c * p[:, 1]
    iy, ix = cell(wx, wy)
    return bool(occ[iy, ix].any())


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    occ, inside = build_world()
    logic = wander.Wanderer(rng=random.Random(seed))
    seen = np.zeros_like(occ)
    log_odds = np.zeros((N, N))
    bx = by = yaw = 0.0
    dt, t = 0.1, 0.0
    collisions = 0
    states = {}
    path_len = 0.0
    while t < seconds:
        lx = bx + math.cos(yaw) * LIDAR_X
        ly = by + math.sin(yaw) * LIDAR_X
        rng, ang = scan(occ, lx, ly, yaw)
        # coverage + ideal map
        steps = np.arange(R_MIN, R_MAX, 0.05)
        for k in range(0, BEAMS, 2):
            r = rng[k] if np.isfinite(rng[k]) else R_MAX
            ss = steps[steps < r]
            iy, ix = cell(lx + ss * math.cos(ang[k]), ly + ss * math.sin(ang[k]))
            seen[iy, ix] = True
            log_odds[iy, ix] -= 0.2
            if np.isfinite(rng[k]):
                iy2, ix2 = cell(np.array([lx + r * math.cos(ang[k])]),
                                np.array([ly + r * math.sin(ang[k])]))
                log_odds[iy2, ix2] += 0.9
        # the robot's scan in its own frame (angle 0 = driving direction)
        own = rng.copy()
        v, w = logic.step(own.tolist(), -math.pi, 2 * math.pi / BEAMS, R_MIN, R_MAX, t)
        states[logic.state] = states.get(logic.state, 0) + 1
        nyaw = yaw + w * dt
        nx = bx + v * math.cos(yaw) * dt
        ny = by + v * math.sin(yaw) * dt
        if body_collides(occ, nx, ny, nyaw):
            collisions += 1                  # robot is blocked by the obstacle
        else:
            path_len += math.hypot(nx - bx, ny - by)
            bx, by, yaw = nx, ny, nyaw
        t += dt
    free = inside.sum()
    cov = (seen & inside).sum() / free
    print(f'sim {seconds:.0f} s, seed {seed}: collisions={collisions}, path={path_len:.1f} m, '
          f'free area seen={100 * cov:.1f} %, states={states}')

    img = np.full((N, N), 205, dtype=np.uint8)
    img[seen] = 254
    img[log_odds > 0.5] = 0
    img = img[::-1, :]
    try:
        from PIL import Image
        Image.fromarray(img).resize((N * 3, N * 3), Image.NEAREST).save(
            os.path.join(PKG, 'maps', 'offline_preview.png'))
    except ImportError:
        pass
    return collisions, cov


if __name__ == '__main__':
    main()
