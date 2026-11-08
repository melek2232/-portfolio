#!/usr/bin/env bash
# Usage: save_map.sh my_room   -> ~/maps/my_room.pgm + ~/maps/my_room.yaml
set -e
name="${1:-my_map}"
mkdir -p "$HOME/maps"
ros2 run nav2_map_server map_saver_cli -f "$HOME/maps/$name" --ros-args -p use_sim_time:=true -p save_map_timeout:=10.0
echo "Saved: $HOME/maps/$name.yaml and $HOME/maps/$name.pgm"
