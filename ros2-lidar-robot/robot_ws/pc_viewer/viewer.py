#!/usr/bin/env python3
"""PC viewer for the lidar scan, the generated map and the lidar data. No ROS needed.

  python3 viewer.py sim                      simulated room, robot explores by itself
  python3 viewer.py live COM5                real YDLIDAR X2 on this PC (Windows: COMx, Linux: /dev/ttyUSB0)
  python3 viewer.py live /dev/ttyUSB0 --csv scan.csv
Options: --save out.png --seconds N (no window, for tests)   --max-range 8

sim : map built with the simulated robot's exact pose (the robot is in a virtual copy of the room).
live: the map is built around the lidar's FIXED position (no motion estimate): keep the lidar still
      (or move it slowly by hand and press r to reset). For a map while driving, use the ROS version.
"""
import argparse
import math
import os
import random
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from x2 import X2Parser  # noqa: E402


class Grid:
    """Log-odds occupancy grid centred on (0,0)."""
    def __init__(self, half=6.0, res=0.05):
        self.half, self.res = half, res
        self.n = int(2 * half / res)
        self.lo = np.zeros((self.n, self.n), np.float32)
        self.seen = np.zeros((self.n, self.n), bool)

    def idx(self, x, y):
        return (np.clip(((y + self.half) / self.res).astype(int), 0, self.n - 1),
                np.clip(((x + self.half) / self.res).astype(int), 0, self.n - 1))

    def add(self, px, py, pts, max_range):
        """pts: array (k,2) of world angle (rad), range (m)."""
        for a, r in pts:
            hit = r < max_range
            r = min(r, max_range)
            ss = np.arange(0.05, r, self.res)
            iy, ix = self.idx(px + ss * math.cos(a), py + ss * math.sin(a))
            self.lo[iy, ix] = np.maximum(self.lo[iy, ix] - 0.3, -4)
            self.seen[iy, ix] = True
            if hit:
                iy, ix = self.idx(np.array([px + r * math.cos(a)]), np.array([py + r * math.sin(a)]))
                self.lo[iy, ix] = np.minimum(self.lo[iy, ix] + 0.9, 6)
                self.seen[iy, ix] = True

    def image(self):
        img = np.full((self.n, self.n), 0.55, np.float32)   # unknown: grey
        img[self.seen & (self.lo <= 0)] = 1.0               # free: white
        img[self.lo > 0.4] = 0.0                            # occupied: black
        return img

    def save_pgm(self, path):
        img = (self.image() * 254).astype(np.uint8)[::-1]
        with open(path, 'wb') as f:
            f.write(b'P5 %d %d 255\n' % (self.n, self.n))
            f.write(img.tobytes())
        with open(path[:-4] + '.yaml', 'w') as f:
            f.write(f'image: {os.path.basename(path)}\nresolution: {self.res}\n'
                    f'origin: [{-self.half}, {-self.half}, 0.0]\nnegate: 0\n'
                    'occupied_thresh: 0.65\nfree_thresh: 0.25\n')


class SimSource:
    def __init__(self, seed=1):
        tools = os.path.join(HERE, '..', 'src', 'robot_description', 'tools')
        sys.path.insert(0, tools)
        import importlib.util
        import offline_check as oc
        self.oc = oc
        self.occ, _ = oc.build_world()
        self.logic = oc.wander.Wanderer(rng=random.Random(seed))
        self.x = self.y = self.yaw = 0.0
        self.t = 0.0
        self.sx = self.sy = 0.0

    def poll(self):
        oc, dt = self.oc, 0.1
        lx = self.x + math.cos(self.yaw) * oc.LIDAR_X
        ly = self.y + math.sin(self.yaw) * oc.LIDAR_X
        rng, ang = oc.scan(self.occ, lx, ly, self.yaw)
        rng = rng + np.random.normal(0, 0.01, rng.shape)        # 1 cm noise
        v, w = self.logic.step(rng.tolist(), -math.pi, 2 * math.pi / oc.BEAMS, oc.R_MIN, oc.R_MAX, self.t)
        nyaw = self.yaw + w * dt
        nx, ny = self.x + v * math.cos(self.yaw) * dt, self.y + v * math.sin(self.yaw) * dt
        if not oc.body_collides(self.occ, nx, ny, nyaw):
            self.x, self.y, self.yaw = nx, ny, nyaw
        self.t += dt
        pts = [(a, r) for a, r in zip(ang, rng) if oc.R_MIN < r < oc.R_MAX]   # world angles
        self.pose = (lx, ly, self.yaw)
        local = [(a - self.yaw, r) for a, r in pts]
        return [dict(local=local, world=pts, pose=self.pose)]


class LiveSource:
    def __init__(self, port, baud, csv):
        import serial
        self.ser = serial.Serial(port, baud, timeout=0.05)
        try:
            self.ser.dtr = True            # motor control on the USB adapter
        except Exception:
            pass
        self.p = X2Parser()
        self.csv = open(csv, 'w') if csv else None
        if self.csv:
            self.csv.write('time,angle_deg,distance_m\n')

    def poll(self):
        out = []
        for scan in self.p.feed(self.ser.read(4096)):
            if self.csv:
                t = time.time()
                for a, r in scan:
                    self.csv.write(f'{t:.3f},{math.degrees(a):.2f},{r:.4f}\n')
            out.append(dict(local=scan, world=scan, pose=(0.0, 0.0, 0.0)))
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['sim', 'live'])
    ap.add_argument('port', nargs='?')
    ap.add_argument('--baud', type=int, default=115200)
    ap.add_argument('--csv')
    ap.add_argument('--max-range', type=float, default=8.0)
    ap.add_argument('--save')
    ap.add_argument('--seconds', type=float, default=0)
    a = ap.parse_args()
    import matplotlib
    if a.save:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    if a.mode == 'live':
        if not a.port:
            sys.exit('give the serial port, e.g. COM5 or /dev/ttyUSB0')
        src = LiveSource(a.port, a.baud, a.csv)
    else:
        src = SimSource()
    grid = Grid()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6.5))
    fig.suptitle('Lidar scan (left) and generated map (right)   keys: r reset map, s save map, q quit')
    ax1.set_title('Live scan, robot frame (x forward)')
    ax1.set_aspect('equal'); ax1.set_xlim(-a.max_range, a.max_range); ax1.set_ylim(-a.max_range, a.max_range)
    for rr in range(1, int(a.max_range) + 1):
        ax1.add_patch(plt.Circle((0, 0), rr, fill=False, color='0.85'))
    sc = ax1.scatter([], [], s=6, c=[], cmap='viridis_r', vmin=0, vmax=a.max_range)
    ax1.plot([0, 0.4], [0, 0], 'r-', lw=3)
    txt = ax1.text(0.02, 0.98, '', transform=ax1.transAxes, va='top', family='monospace',
                   bbox=dict(fc='white', alpha=0.8))
    ax2.set_title('Occupancy map (black wall, white free, grey unknown)')
    im = ax2.imshow(grid.image(), cmap='gray', vmin=0, vmax=1, origin='lower',
                    extent=[-grid.half, grid.half, -grid.half, grid.half])
    trail, = ax2.plot([], [], 'c-', lw=1)
    robot, = ax2.plot([], [], 'ro', ms=6)
    path = []
    state = dict(turns=0, t0=time.time(), last=time.time(), hz=0.0)

    def reset():
        grid.lo[:] = 0; grid.seen[:] = False; path.clear()

    def save_map():
        d = os.path.expanduser('~/maps'); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, time.strftime('map_%Y%m%d_%H%M%S.pgm')); grid.save_pgm(p)
        print('map saved to', p, 'and the .yaml next to it')

    def onkey(e):
        if e.key == 'r': reset()
        elif e.key == 's': save_map()
        elif e.key == 'q': plt.close(fig)
    fig.canvas.mpl_connect('key_press_event', onkey)

    def step():
        for s in src.poll():
            now = time.time()
            state['hz'] = 0.8 * state['hz'] + 0.2 / max(now - state['last'], 1e-3)
            state['last'] = now
            state['turns'] += 1
            grid.add(s['pose'][0], s['pose'][1], s['world'], a.max_range)
            path.append(s['pose'][:2])
            loc = np.array(s['local']) if len(s['local']) else np.zeros((0, 2))
            if len(loc):
                m = loc[:, 1] < a.max_range
                loc = loc[m]
                sc.set_offsets(np.c_[loc[:, 1] * np.cos(loc[:, 0]), loc[:, 1] * np.sin(loc[:, 0])])
                sc.set_array(loc[:, 1])
                near = loc[loc[:, 1].argmin()] if len(loc) else None
                txt.set_text(f'scans: {state["turns"]}   rate: {state["hz"]:.1f} Hz\n'
                             f'points/scan: {len(loc)}\n'
                             + (f'nearest: {near[1]:.2f} m at {math.degrees(near[0]):.0f} deg\n' if near is not None else '')
                             + (f'pose: x={s["pose"][0]:.2f} y={s["pose"][1]:.2f}\n' if a.mode == 'sim' else ''))
        im.set_data(grid.image())
        if path:
            p = np.array(path)
            trail.set_data(p[:, 0], p[:, 1]); robot.set_data([p[-1, 0]], [p[-1, 1]])

    if a.save or a.seconds:
        end = time.time() + (a.seconds or 8)
        while time.time() < end and (a.mode == 'live' or state['turns'] < (a.seconds or 8) * 10):
            step()
        step()
        if a.save:
            fig.savefig(a.save, dpi=80)
            print('saved', a.save, 'scans', state['turns'])
        return
    timer = fig.canvas.new_timer(interval=50)
    timer.add_callback(lambda: (step(), fig.canvas.draw_idle()))
    timer.start()
    plt.show()


if __name__ == '__main__':
    main()
