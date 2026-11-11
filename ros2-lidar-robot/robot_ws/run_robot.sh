#!/usr/bin/env bash
# On the Raspberry Pi: starts the whole robot (v2). It does NOT move by itself: choose the mode from the PC
# (panel.sh: Stop / Manual / Explore / Navigate), or start already in a mode:  MODE=explore ./run_robot.sh
#   NAV=true ./run_robot.sh     also starts Nav2 (click-to-go)       BACKEND=dry_run ./run_robot.sh   no motors
#   ODOM=wheels ./run_robot.sh  wheel odometry instead of the lidar odometry (robot.env: ODOM=lidar)
# Settings (ports, domain id, speed): robot.env.   Stop: Ctrl+C.
cd "$(dirname "$0")"
set -a; [ -f robot.env ] && . ./robot.env; set +a
DISTRO="${ROS_DISTRO:-$(ls /opt/ros | head -n1)}"
# shellcheck disable=SC1090
source "/opt/ros/$DISTRO/setup.bash"
source install/setup.bash
exec ros2 launch robot_base bringup.launch.py \
  lidar:="${LIDAR:-x2}" port:="${LIDAR_PORT:-/dev/ttyUSB0}" \
  backend:="${BACKEND:-serial}" serial_port:="${MEGA_PORT:-/dev/ttyACM0}" \
  lidar_yaw:="${LIDAR_YAW:-0.0}" initial_mode:="${MODE:-manual}" \
  explore_speed:="${SPEED:-0.12}" nav:="${NAV:-false}" odom:="${ODOM:-lidar}" rviz:=false
