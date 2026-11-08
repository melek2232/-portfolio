#!/usr/bin/env python3
"""Rasterises worlds/mapping_room.sdf into an ideal occupancy map (maps/mapping_room_truth.*).

This is the ground truth of the simulated room, handy to test Nav2 without mapping first
and to compare with what SLAM produced.  Usage: python3 tools/make_truth_map.py
"""
import math
import os
import xml.etree.ElementTree as ET

import numpy as np

RES = 0.05
HALF = 5.0                      # map covers [-5, 5] m in x and y
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)


def load_shapes(sdf_path):
    shapes = []
    root = ET.parse(sdf_path).getroot()
    for model in root.iter('model'):
        if model.get('name') == 'ground_plane':
            continue
        pose = [float(v) for v in model.find('pose').text.split()]
        geom = model.find('.//collision/geometry')
        box = geom.find('box')
        cyl = geom.find('cylinder')
        if box is not None:
            sx, sy, _ = [float(v) for v in box.find('size').text.split()]
            shapes.append(('box', pose[0], pose[1], pose[5], sx, sy))
        elif cyl is not None:
            shapes.append(('cyl', pose[0], pose[1], 0.0, float(cyl.find('radius').text), 0.0))
    return shapes


def occupied_mask(shapes, xs, ys):
    X, Y = np.meshgrid(xs, ys)
    occ = np.zeros(X.shape, dtype=bool)
    for kind, cx, cy, yaw, a, b in shapes:
        dx, dy = X - cx, Y - cy
        if kind == 'box':
            c, s = math.cos(-yaw), math.sin(-yaw)
            lx, ly = c * dx - s * dy, s * dx + c * dy
            occ |= (np.abs(lx) <= a / 2) & (np.abs(ly) <= b / 2)
        else:
            occ |= dx * dx + dy * dy <= a * a
    return occ


def main():
    shapes = load_shapes(os.path.join(PKG, 'worlds', 'mapping_room.sdf'))
    n = int(2 * HALF / RES)
    xs = -HALF + (np.arange(n) + 0.5) * RES
    ys = -HALF + (np.arange(n) + 0.5) * RES
    occ = occupied_mask(shapes, xs, ys)
    # outer walls are the 4 largest boxes: everything outside them is unknown
    X, Y = np.meshgrid(xs, ys)
    inside = (np.abs(X) < 3.9) & (np.abs(Y) < 3.9)
    img = np.full((n, n), 205, dtype=np.uint8)      # unknown
    img[inside] = 254                               # free
    img[occ] = 0                                    # occupied
    img = img[::-1, :]                              # image row 0 = top = max y
    os.makedirs(os.path.join(PKG, 'maps'), exist_ok=True)
    pgm = os.path.join(PKG, 'maps', 'mapping_room_truth.pgm')
    with open(pgm, 'wb') as f:
        f.write(f'P5\n{n} {n}\n255\n'.encode())
        f.write(img.tobytes())
    with open(os.path.join(PKG, 'maps', 'mapping_room_truth.yaml'), 'w') as f:
        f.write('image: mapping_room_truth.pgm\nmode: trinary\n'
                f'resolution: {RES}\norigin: [{-HALF}, {-HALF}, 0.0]\n'
                'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n')
    try:
        from PIL import Image
        Image.fromarray(img).resize((n * 3, n * 3), Image.NEAREST).save(
            os.path.join(PKG, 'maps', 'mapping_room_truth.png'))
    except ImportError:
        pass
    print(f'{len(shapes)} shapes -> maps/mapping_room_truth.pgm ({n}x{n}, {RES} m/px)')


if __name__ == '__main__':
    main()
