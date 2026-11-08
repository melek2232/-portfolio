#!/usr/bin/env bash
# Offline tests: no ROS, no Gazebo, no Arduino needed. Requires: g++, python3, numpy, pyserial.
set -e
cd "$(dirname "$0")"
echo "== Mega firmware (compiled with PC stand-ins)";   firmware/host_test/run_tests.sh
echo "== Pi serial link <-> simulated Mega";            python3 -I src/robot_base/test/test_serial_e2e.py | tail -3
echo "== base node (ROS replaced by stand-ins)";        python3 -I src/robot_base/test/test_base_node_smoke.py | tail -2
echo "== motor / odometry maths"
python3 -I - <<'PY'
import sys, importlib.util
sys.path.insert(0, 'src/robot_base')
spec = importlib.util.spec_from_file_location('t', 'src/robot_base/test/test_kinematics.py')
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
n = 0
for name in sorted(dir(t)):
    if name.startswith('test_'):
        getattr(t, name)(); n += 1
print(n, 'tests passed')
PY
echo "== exploration logic (simulated room, 5 min)";    python3 -I src/robot_description/tools/offline_check.py 300 1
echo "== fake_robot node (ROS replaced by stand-ins)"
python3 src/robot_description/test/test_fake_robot.py
echo "== explorer logic (rotated lidar, wall ahead)"
python3 src/robot_base/test/test_explore_logic.py
echo "== v2: command arbitration, safety layer, scan filter, health"
python3 src/robot_base/test/test_mux_filter.py | tail -3
echo "== v2: robot + safety layer + explorer in the simulated room"
python3 src/robot_base/test/test_sim_integration.py | tail -6
echo "== v2: web panel (HTTP server + browser; skipped if Playwright is missing)"
if python3 -c "import playwright" 2>/dev/null; then python3 pc/web_panel/test_panel.py | tail -3; else echo "(skipped: pip install playwright)"; fi
echo "== pc_viewer (X2 parser + live mode)"
python3 pc_viewer/test_x2.py
echo "ALL OFFLINE TESTS DONE"
