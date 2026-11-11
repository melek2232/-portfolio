#!/usr/bin/env python3
"""Offline checks of the Nav2 parameter merge and the odometry selection (no ROS needed).

The robot's overlays are also merged onto Nav2's real default file ($NAV2_PARAMS, else the installed
nav2_bringup, else the Jazzy copy in fixtures/) and the result is checked for the bugs found in simulation:
MPPI model_dt vs controller period, base_footprint frames, controller plugin.
"""
import glob
import os
import sys
import tempfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, '..')
sys.path.insert(0, PKG)
from robot_base import odom_select  # noqa: E402
from robot_base.nav2_params import build, deep_merge  # noqa: E402

fails = 0


def check(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + (f'   {info}' if info and not cond else ''))
    fails += 0 if cond else 1


# ---- deep_merge
d = deep_merge({'a': {'x': 1, 'y': 2}, 'b': 1}, {'a': {'y': 3}, 'c': 4})
check('merge keeps untouched keys and overrides nested ones', d == {'a': {'x': 1, 'y': 3}, 'b': 1, 'c': 4})
d = deep_merge({'c': {'FollowPath': {'plugin': 'mppi', 'vx_std': 0.2}}},
               {'c': {'FollowPath': {'__replace__': True, 'plugin': 'rpp', 'desired_linear_vel': 0.15}}})
check('__replace__ swaps the subtree (no leftover keys, marker removed)',
      d == {'c': {'FollowPath': {'plugin': 'rpp', 'desired_linear_vel': 0.15}}}, d)

# ---- build with several overlays, later wins; single path still accepted
tmp = tempfile.mkdtemp()
def w(name, data):
    p = os.path.join(tmp, name)
    with open(p, 'w') as f:
        yaml.safe_dump(data, f)
    return p
base = w('base.yaml', {'n': {'ros__parameters': {'v': 1, 'k': 'keep'}}})
o1 = w('o1.yaml', {'n': {'ros__parameters': {'v': 2}}})
o2 = w('o2.yaml', {'n': {'ros__parameters': {'v': 3}}})
out = os.path.join(tmp, 'out.yaml')
build(base, [o1, o2], out)
check('build: overlays applied in order', yaml.safe_load(open(out))['n']['ros__parameters'] == {'v': 3, 'k': 'keep'})
build(base, o1, out)
check('build: a single overlay path still works', yaml.safe_load(open(out))['n']['ros__parameters']['v'] == 2)

# ---- odometry selection
check('odom default is lidar', odom_select.resolve('', True) == ('lidar', None))
m, warn = odom_select.resolve('lidar', False)
check('lidar without rf2o falls back to wheels with a warning', m == 'wheels' and 'rf2o' in warn)
check('wheels stays wheels', odom_select.resolve('WHEELS', False) == ('wheels', None))
try:
    odom_select.resolve('gps', True); check('unknown odom mode rejected', False)
except ValueError:
    check('unknown odom mode rejected', True)
p = odom_select.base_node_params('lidar')
check('lidar: base_node leaves /odom and TF to rf2o',
      p['odom_topic'] == '/odom_wheels' and p['publish_tf'] is False)

# ---- the robot's overlays on the real Nav2 defaults (if installed)
cfg = os.path.join(PKG, 'config')
defaults = os.environ.get('NAV2_PARAMS') or next(iter(sorted(glob.glob(
    '/opt/ros/*/share/nav2_bringup/params/nav2_params.yaml') + glob.glob(
    os.path.join(os.environ.get('CONDA_PREFIX', '/nonexistent'), 'share/nav2_bringup/params/nav2_params.yaml')))),
    os.path.join(HERE, 'fixtures', 'nav2_params_jazzy.yaml'))
print(f'Nav2 defaults: {defaults}')
for overlays in (['nav2_overrides.yaml'], ['nav2_overrides.yaml', 'nav2_lidar_odom.yaml']):
    paths = [os.path.join(cfg, o) for o in overlays]
    for path in paths:
        with open(path) as f:
            yaml.safe_load(f)
    if not defaults:
        continue
    build(defaults, paths, out)
    P = yaml.safe_load(open(out))
    tag = '+'.join(o.replace('nav2_', '').replace('.yaml', '') for o in overlays)
    cs = P['controller_server']['ros__parameters']
    fp = cs['FollowPath']
    if 'MPPI' in fp['plugin']:
        ok = fp['model_dt'] >= 1.0 / cs['controller_frequency'] - 1e-9
        check(f'[{tag}] MPPI model_dt >= controller period', ok, f"{fp['model_dt']} vs {cs['controller_frequency']} Hz")
    else:
        check(f'[{tag}] controller is Regulated Pure Pursuit, no MPPI leftovers',
              'RegulatedPurePursuit' in fp['plugin'] and 'vx_std' not in fp and '__replace__' not in fp)
    bad = [k for k, v in P.items() if k != 'loopback_simulator' and 'base_footprint' in yaml.safe_dump(v)]
    check(f'[{tag}] no base_footprint frame (robot root is base_link)', not bad, bad)
    vs = P['velocity_smoother']['ros__parameters']
    check(f'[{tag}] velocity limits <= base_node clamps (0.20 m/s, 1.5 rad/s)',
          vs['max_velocity'][0] <= 0.20 and vs['max_velocity'][2] <= 1.5, vs['max_velocity'])
    if 'lidar' in tag:
        check(f'[{tag}] slow rotation for lidar odometry', vs['max_velocity'][2] <= 0.6
              and fp['rotate_to_heading_angular_vel'] <= 0.6)

print('ALL PASSED' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
