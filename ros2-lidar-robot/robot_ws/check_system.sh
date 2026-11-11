#!/usr/bin/env bash
# On the Pi, while run_robot.sh is running (second terminal):  ./check_system.sh
# Prints OK / PROBLEM for each layer, from USB up to the map.
cd "$(dirname "$0")"
set -a; [ -f robot.env ] && . ./robot.env; set +a
DISTRO="${ROS_DISTRO:-$(ls /opt/ros | head -n1)}"
source "/opt/ros/$DISTRO/setup.bash"; source install/setup.bash
ok()  { echo "  OK       $*"; }
bad() { echo "  PROBLEM  $*"; }
echo "1. USB devices"
[ -e "$MEGA_PORT" ]  && ok "Arduino Mega: $MEGA_PORT"   || bad "Arduino Mega not found ($MEGA_PORT)"
[ -e "$LIDAR_PORT" ] && ok "lidar: $LIDAR_PORT"         || bad "lidar not found ($LIDAR_PORT)"
oc=$(dmesg 2>/dev/null | grep -c "over-current")
[ "${oc:-0}" -gt 0 ] && bad "USB over-current events in dmesg: $oc (power supply / short)" || ok "no USB over-current"
echo "2. ROS nodes"
nodes=$(timeout 6 ros2 node list 2>/dev/null)
NODES="ydlidar_ros2_driver_node base_node scan_filter cmd_mux slam_toolbox health"
[ "${ODOM:-lidar}" = lidar ] && NODES="$NODES rf2o_laser_odometry"
for n in $NODES; do
  echo "$nodes" | grep -q "$n" && ok "$n" || bad "$n is not running"
done
[ "${ODOM:-lidar}" = lidar ] && [ ! -d install/rf2o_laser_odometry ] && bad "rf2o not built: ./setup_pi.sh"
echo "3. Topic rates (3 s each)"
for t in /scan /scan_filtered /odom /map; do
  r=$(timeout 6 ros2 topic hz "$t" --window 5 2>/dev/null | grep -m1 "average rate" | awk '{print $3}')
  [ -n "$r" ] && ok "$t  $r Hz" || bad "$t: no messages"
done
echo "4. SLAM and transforms"
st=$(timeout 5 ros2 lifecycle get /slam_toolbox 2>/dev/null)
echo "$st" | grep -q active && ok "slam_toolbox active" || bad "slam_toolbox: ${st:-no answer}"
timeout 6 ros2 run tf2_ros tf2_echo map base_link 2>/dev/null | grep -m1 -q Translation \
  && ok "TF map -> base_link" || bad "TF map -> base_link missing (SLAM has no map yet?)"
timeout 6 ros2 run tf2_ros tf2_echo odom base_link 2>/dev/null | grep -m1 -q Translation \
  && ok "TF odom -> base_link (odometry: ${ODOM:-lidar})" || bad "TF odom -> base_link missing (odometry: ${ODOM:-lidar})"
echo "5. Robot health"
timeout 5 ros2 topic echo --once --field data /robot_health 2>/dev/null || bad "no /robot_health"
timeout 5 ros2 topic echo --once --field data /robot_state 2>/dev/null || bad "no /robot_state"
