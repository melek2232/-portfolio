#!/usr/bin/env bash
# On your PC: emergency stop (software).   ./pc/estop.sh        release:  ./pc/estop.sh release
. "$(dirname "$0")/_common.sh"
if [ "$1" = "release" ]; then v=false; else v=true; fi
ros_run "ros2 topic pub --times 5 -r 10 /estop std_msgs/msg/Bool '{data: $v}'"
