import math

from robot_base import kinematics as k


def test_straight_line():
    vl, vr = k.wheel_speeds(0.2, 0.0, 0.15)
    assert vl == vr == 0.2


def test_turn_in_place_is_symmetric():
    vl, vr = k.wheel_speeds(0.0, 1.0, 0.2)
    assert math.isclose(vl, -0.1) and math.isclose(vr, 0.1)


def test_roundtrip_body_wheels():
    vl, vr = k.wheel_speeds(0.12, 0.5, 0.1471)
    v, w = k.body_velocity(vl, vr, 0.1471)
    assert math.isclose(v, 0.12) and math.isclose(w, 0.5)


def test_duty_deadband_and_min_duty():
    assert k.speed_to_duty(0.001, 0.3, 0.25) == 0.0              # inside the dead band
    assert math.isclose(k.speed_to_duty(0.03, 0.3, 0.25), 0.25 + 0.75 * 0.1)
    assert math.isclose(k.speed_to_duty(-0.03, 0.3, 0.25), -(0.25 + 0.75 * 0.1))
    assert k.speed_to_duty(1.0, 0.3, 0.25) == 1.0                # saturated
    assert math.isclose(k.speed_to_duty(0.3, 0.3, 0.25), 1.0)    # exactly full speed
    a = k.speed_to_duty(0.10, 0.3, 0.25)
    b = k.speed_to_duty(0.12, 0.3, 0.25)
    assert b > a                                                  # monotonic (still controllable)


def test_integrate_circle_returns_to_start():
    x = y = th = 0.0
    v, w, dt = 0.1, 0.5, 0.01
    for _ in range(int(2 * math.pi / w / dt)):
        x, y, th = k.integrate(x, y, th, v, w, dt)
    assert abs(x) < 0.01 and abs(y) < 0.01


def test_slew_limits_step():
    assert k.slew(0.0, 1.0, 0.1) == 0.1
    assert k.slew(0.5, 0.0, 0.1) == 0.4
    assert k.slew(0.05, 0.0, 0.1) == 0.0


def test_normalize_angle():
    assert math.isclose(k.normalize_angle(3 * math.pi), math.pi) or \
        math.isclose(k.normalize_angle(3 * math.pi), -math.pi)


def test_ticks_straight_and_turn():
    d, dth = k.ticks_to_motion(500, 500, 1000.0, 1000.0, 0.1471)
    assert math.isclose(d, 0.5) and math.isclose(dth, 0.0, abs_tol=1e-12)
    d, dth = k.ticks_to_motion(-100, 100, 1000.0, 1000.0, 0.2)
    assert math.isclose(d, 0.0, abs_tol=1e-12) and math.isclose(dth, 1.0)    # 0.2 m / 0.2 m


def test_ticks_scales_and_unequal_wheels():
    d, dth = k.ticks_to_motion(1000, 1000, 1000.0, 2000.0, 0.2, lin_scale=2.0, ang_scale=0.5)
    # left 1.0 m, right 0.5 m
    assert math.isclose(d, 2.0 * 0.75) and math.isclose(dth, 0.5 * (0.5 - 1.0) / 0.2)


def test_integrate_delta_matches_integrate():
    a = k.integrate(0.0, 0.0, 0.3, 0.2, 0.4, 0.5)
    b = k.integrate_delta(0.0, 0.0, 0.3, 0.2 * 0.5, 0.4 * 0.5)
    assert all(math.isclose(x, y) for x, y in zip(a, b))
