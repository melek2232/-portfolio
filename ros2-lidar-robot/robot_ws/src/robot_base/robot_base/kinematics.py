"""Pure-Python skid-steer maths (no ROS), so it can be unit-tested anywhere."""
import math


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def normalize_angle(a):
    return math.atan2(math.sin(a), math.cos(a))


def wheel_speeds(v, w, separation):
    """Body (v m/s forward, w rad/s counter-clockwise) -> (left, right) side speeds in m/s."""
    return v - w * separation / 2.0, v + w * separation / 2.0


def speed_to_duty(speed, max_speed, min_duty):
    """Side speed (m/s) -> PWM duty in [-1, 1].

    max_speed is the speed at 100 % PWM. Tiny commands give 0; otherwise the duty runs from
    min_duty (the PWM at which the motors just start to turn) up to 1.0, so slow speeds stay
    controllable instead of being stuck below the stall threshold.
    """
    d = clamp(speed / max_speed, -1.0, 1.0)
    a = abs(d)
    if a < 0.02:
        return 0.0
    return math.copysign(min_duty + (1.0 - min_duty) * a, d)


def body_velocity(vl, vr, separation, lin_scale=1.0, ang_scale=1.0):
    """(left, right) side speeds -> body (v, w), with calibration factors."""
    return lin_scale * (vl + vr) / 2.0, ang_scale * (vr - vl) / separation


def slew(current, target, max_step):
    return current + clamp(target - current, -max_step, max_step)


def integrate(x, y, th, v, w, dt):
    mid = th + 0.5 * w * dt
    return (x + v * math.cos(mid) * dt,
            y + v * math.sin(mid) * dt,
            normalize_angle(th + w * dt))


def yaw_to_quaternion(yaw):
    return 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)


def integrate_delta(x, y, th, d, dth):
    """Integrate a travelled distance d (m) and heading change dth (rad)."""
    mid = th + 0.5 * dth
    return (x + d * math.cos(mid), y + d * math.sin(mid), normalize_angle(th + dth))


def ticks_to_motion(dl_ticks, dr_ticks, tpm_left, tpm_right, separation,
                    lin_scale=1.0, ang_scale=1.0):
    """Encoder tick increments of the left/right side -> (distance m, heading change rad)."""
    dl = dl_ticks / tpm_left
    dr = dr_ticks / tpm_right
    return lin_scale * (dl + dr) / 2.0, ang_scale * (dr - dl) / separation
