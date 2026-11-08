"""Command arbitration + safety layer (pure logic, no ROS: tested offline).

One source drives the robot at a time, chosen by the MODE:
    stop     nothing moves
    manual   /cmd_vel_teleop   (PC panel, keyboard, gamepad)
    explore  /cmd_vel_auto     (the autonomous explorer)
    nav      /cmd_vel         (Nav2: click a goal on the map)
Whatever the source, the output goes through the safety layer:
    * e-stop latched            -> zero
    * source silent > timeout   -> zero   (dead-man: release the key and the robot stops)
    * lidar silent > timeout    -> zero   (blind robot does not move)
    * obstacle ahead (or behind when reversing) -> slow down, stop at stop_distance
    * speeds clamped
This is a software layer: it does NOT replace a physical power cut-off on the motor battery.
"""
import math

INF = float('inf')
MODES = ('stop', 'manual', 'explore', 'nav')
SOURCES = ('manual', 'explore', 'nav')


def corridor_clearance(ranges, a_min, a_inc, r_min, r_max, front_off, rear_off,
                       half_w, margin, hits=2):
    """Free distance (from the body, not from the lidar) ahead and behind, inside the corridor
    the body sweeps when driving straight. `a_min` must already include the lidar mounting yaw.
    The `hits`-th nearest point is used so one noisy point does not stop the robot."""
    fronts, rears = [], []
    w = half_w + margin
    for i, r in enumerate(ranges):
        if r != r or math.isinf(r) or r < r_min or r > r_max:
            continue
        a = a_min + i * a_inc
        x, y = r * math.cos(a), r * math.sin(a)
        if abs(y) > w:
            continue
        if x > 0.0:
            fronts.append(x - front_off)
        elif x < 0.0:
            rears.append(-x - rear_off)

    def pick(values):
        if len(values) < hits:
            return INF
        values.sort()
        return max(values[hits - 1], 0.0)
    return pick(fronts), pick(rears)


def speed_scale(distance, stop_distance, slow_distance):
    if distance <= stop_distance:
        return 0.0
    if distance >= slow_distance:
        return 1.0
    return (distance - stop_distance) / (slow_distance - stop_distance)


class Mux:
    DEFAULTS = dict(initial_mode='manual', source_timeout=0.5, scan_timeout=1.0,
                    stop_distance=0.10, slow_distance=0.45, block_when_blind=True,
                    max_linear=0.20, max_angular=1.2)

    def __init__(self, **cfg):
        self.cfg = dict(self.DEFAULTS)
        self.cfg.update(cfg)
        mode = self.cfg['initial_mode']
        self.mode = mode if mode in MODES else 'stop'
        self.estopped = False
        self.cmds = {}
        self.front = INF
        self.rear = INF
        self.scan_t = None

    # ---------------------------------------------------------------- inputs
    def set_mode(self, mode):
        mode = str(mode).strip().lower()
        if mode not in MODES:
            return False
        if self.estopped and mode != 'stop':
            return False            # release the e-stop first
        self.mode = mode
        return True

    def set_estop(self, flag):
        if flag:
            self.estopped = True
            self.mode = 'stop'
        else:
            self.estopped = False   # mode stays 'stop': choose a mode explicitly to move again

    def on_cmd(self, source, v, w, t):
        if source in SOURCES:
            self.cmds[source] = (float(v), float(w), t)

    def on_clearance(self, front, rear, t):
        self.front, self.rear, self.scan_t = front, rear, t

    # ---------------------------------------------------------------- output
    def step(self, t):
        """-> (linear, angular, info)"""
        c = self.cfg
        info = dict(mode=self.mode, estop=self.estopped, front=self.front, rear=self.rear,
                    reason='ok', limited=False,
                    blind=(self.scan_t is None or t - self.scan_t > c['scan_timeout']))
        if self.estopped:
            info['reason'] = 'estop'
            return 0.0, 0.0, info
        if self.mode == 'stop':
            info['reason'] = 'stop'
            return 0.0, 0.0, info
        cmd = self.cmds.get(self.mode)
        if cmd is None or t - cmd[2] > c['source_timeout']:
            info['reason'] = 'no_command'
            return 0.0, 0.0, info
        v = max(-c['max_linear'], min(c['max_linear'], cmd[0]))
        w = max(-c['max_angular'], min(c['max_angular'], cmd[1]))
        if (v != 0.0 or w != 0.0) and info['blind'] and c['block_when_blind']:
            info['reason'] = 'blind'
            return 0.0, 0.0, info
        if not info['blind']:
            if v > 0.0:
                s = speed_scale(self.front, c['stop_distance'], c['slow_distance'])
            elif v < 0.0:
                s = speed_scale(self.rear, c['stop_distance'], c['slow_distance'])
            else:
                s = 1.0
            if s < 1.0:
                info['limited'] = True
                info['reason'] = 'obstacle'
            v *= s
        return v, w, info
