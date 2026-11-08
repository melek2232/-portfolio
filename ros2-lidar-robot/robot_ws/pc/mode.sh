#!/usr/bin/env bash
# On your PC: change the robot mode without the panel.   ./pc/mode.sh stop|manual|explore|nav
. "$(dirname "$0")/_common.sh"
case "$1" in stop|manual|explore|nav) ;; *) echo "usage: $0 stop|manual|explore|nav"; exit 1;; esac
ros_run "ros2 topic pub --once /robot_mode std_msgs/msg/String '{data: $1}'"
