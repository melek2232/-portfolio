#!/usr/bin/env bash
# Usage: save_map.sh my_room   -> ~/maps/my_room.pgm + .yaml (for Nav2) and ~/maps/my_room.posegraph (to keep mapping later)
set -e
name="${1:-my_map}"
mkdir -p "$HOME/maps"
ros2 run nav2_map_server map_saver_cli -f "$HOME/maps/$name" --ros-args -p save_map_timeout:=10.0
echo "Saved: $HOME/maps/$name.yaml"
ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph "{filename: '$HOME/maps/$name'}" >/dev/null 2>&1 \
  && echo "Pose graph saved: $HOME/maps/$name.posegraph" || echo "(pose graph not saved: optional)"
