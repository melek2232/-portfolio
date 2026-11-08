#!/usr/bin/env bash
# FRESH INSTALL on the robot's Raspberry Pi 5.  Run once:   ./setup_pi.sh
# Needs ROS 2 already installed (Jazzy on Ubuntu 24.04, or Lyrical). No Gazebo here.
set -e
cd "$(dirname "$0")"
DISTRO="${ROS_DISTRO:-$(ls /opt/ros 2>/dev/null | head -n1)}"
if [ -z "$DISTRO" ] || [ ! -f "/opt/ros/$DISTRO/setup.bash" ]; then
  echo "ROS 2 not found in /opt/ros. Install ROS 2 first (ros-$DISTRO-ros-base)."
  exit 1
fi
echo ">> ROS 2 $DISTRO"

sudo apt update
sudo apt install -y "ros-$DISTRO-navigation2" "ros-$DISTRO-nav2-bringup" "ros-$DISTRO-slam-toolbox" \
  "ros-$DISTRO-teleop-twist-keyboard" "ros-$DISTRO-rviz2" "ros-$DISTRO-robot-state-publisher" \
  "ros-$DISTRO-tf2-ros" "ros-$DISTRO-tf2-tools" python3-serial python3-yaml python3-numpy \
  python3-colcon-common-extensions python3-venv python3-pip git build-essential pkg-config

# YDLidar SDK (needs CMake < 4: built with a private CMake 3 from pip)
if ! ldconfig -p | grep -q ydlidar_sdk; then
  echo ">> Installing the YDLidar SDK"
  [ -d "$HOME/YDLidar-SDK" ] || git clone https://github.com/YDLIDAR/YDLidar-SDK.git "$HOME/YDLidar-SDK"
  [ -x "$HOME/.cmake3-venv/bin/cmake" ] || { python3 -m venv "$HOME/.cmake3-venv" && "$HOME/.cmake3-venv/bin/pip" install -q "cmake<4"; }
  rm -rf "$HOME/YDLidar-SDK/build"; mkdir -p "$HOME/YDLidar-SDK/build"
  (cd "$HOME/YDLidar-SDK/build" && "$HOME/.cmake3-venv/bin/cmake" .. -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
     && make -j2 && sudo make install)
  sudo ldconfig
fi

# serial ports of the lidar and the Mega
sudo usermod -aG dialout "$USER"

source "/opt/ros/$DISTRO/setup.bash"
# one job at a time: the Pi can run out of memory while compiling
MAKEFLAGS="-j2" colcon build --symlink-install --executor sequential --parallel-workers 1 \
  --packages-select ydlidar_ros2_driver robot_lidar robot_base \
  --cmake-args -DCMAKE_POLICY_VERSION_MINIMUM=3.5

chmod +x run_robot.sh check_system.sh install_service.sh pc/*.sh firmware/tools/*.py src/robot_base/scripts/*.sh 2>/dev/null || true
cat <<MSG

Build done. NEXT:
 1. LOG OUT AND IN (or reboot) once: serial permission.
 2. Upload firmware/mega_motor_driver/mega_motor_driver.ino to the Mega (Arduino IDE on your PC, board
    "Arduino Mega 2560"; edit the pins at the top first, see firmware/README.md).
 3. Plug lidar + Mega in the Pi, test the motors:  python3 firmware/tools/arduino_test.py   (robot on blocks)
 4. Start the robot:   ./run_robot.sh        (it does not move until you choose a mode)
 5. On your PC:        ./pc/panel.sh          then open http://localhost:8080   (README.md)
MSG
