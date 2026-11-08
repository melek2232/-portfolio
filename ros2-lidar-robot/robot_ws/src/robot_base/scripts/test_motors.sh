#!/usr/bin/env bash
# Short motor test. Run with the robot ON BLOCKS (wheels in the air) the first time.
# Needs: ros2 launch robot_base robot.launch.py   (backend:=serial) in another terminal.
set -e
pulse() {  # linear angular seconds
  echo ">>> linear=$1 angular=$2 for $3 s"
  timeout "$3" ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist \
    "{linear: {x: $1}, angular: {z: $2}}" > /dev/null || true
  sleep 1
}
pulse 0.10 0.0 2     # forward
pulse -0.10 0.0 2    # backward
pulse 0.0 0.8 2      # turn left (counter-clockwise)
pulse 0.0 -0.8 2     # turn right
echo "Done. If a side spins the wrong way: invert_left / invert_right in config/base.yaml."
