#!/usr/bin/env bash
# On your PC: drive with the terminal keyboard (alternative to the panel). Set the mode to manual first.
#   Hold a key: the robot moves; release: it stops (0.5 s dead-man).   Quit: Ctrl+C
. "$(dirname "$0")/_common.sh"
exec $DOCKER run --rm -it --net=host "${ENVARGS[@]}" "$IMAGE" bash -c \
  "source /opt/ros/jazzy/setup.bash && ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/cmd_vel_teleop -p speed:=0.10 -p turn:=0.6"
