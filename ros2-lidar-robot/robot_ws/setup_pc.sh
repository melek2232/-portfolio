#!/usr/bin/env bash
# One-time setup + build on your PC (Ubuntu 24.04 + ROS 2 Jazzy).
#   ./setup_pc.sh              simulation + YDLIDAR driver (SDK + ROS driver) + real-robot packages   <- start here
#   ./setup_pc.sh --no-lidar   simulation only
#   (on the robot's Raspberry Pi use setup_pi.sh)
set -e
cd "$(dirname "$0")"
DISTRO="${ROS_DISTRO:-$(ls /opt/ros 2>/dev/null | head -n1)}"; DISTRO="${DISTRO:-lyrical}"
if [ ! -f "/opt/ros/$DISTRO/setup.bash" ]; then
  echo "ROS 2 '$DISTRO' not found in /opt/ros. Install it first (or run: source /opt/ros/<distro>/setup.bash)."
  exit 1
fi

sudo apt update
sudo apt install -y "ros-$DISTRO-navigation2" "ros-$DISTRO-nav2-bringup" \
  "ros-$DISTRO-slam-toolbox" "ros-$DISTRO-robot-state-publisher" "ros-$DISTRO-rviz2" \
  "ros-$DISTRO-teleop-twist-keyboard" python3-colcon-common-extensions python3-yaml python3-numpy \
  git cmake pkg-config build-essential libboost-dev libeigen3-dev

# Gazebo bridge: optional (only for sim.launch.py; sim_lite.launch.py does not need it)
sudo apt install -y "ros-$DISTRO-ros-gz" || echo ">> ros-$DISTRO-ros-gz not available: skip Gazebo, use sim_lite.launch.py"

# simulation with lidar odometry (sim_lite.launch.py odom:=lidar) needs rf2o + robot_base (pure Python)
./fetch_rf2o.sh
PKGS="robot_description robot_base rf2o_laser_odometry"
if [ "$1" != "--no-lidar" ]; then
  if ! ldconfig -p | grep -q ydlidar_sdk; then
    echo ">> Installing the YDLidar SDK (needed by the driver)"
    [ -d "$HOME/YDLidar-SDK" ] || git clone https://github.com/YDLIDAR/YDLidar-SDK.git "$HOME/YDLidar-SDK"
    # The SDK needs CMake < 4 (it uses removed policies), so build it with a private CMake 3.x from pip
    sudo apt install -y python3-venv python3-pip
    python3 -m venv "$HOME/.cmake3-venv" && "$HOME/.cmake3-venv/bin/pip" install -q "cmake<4"
    rm -rf "$HOME/YDLidar-SDK/build"
    mkdir -p "$HOME/YDLidar-SDK/build" && (cd "$HOME/YDLidar-SDK/build" && "$HOME/.cmake3-venv/bin/cmake" .. && make -j2 && sudo make install)
    sudo ldconfig
  fi
  sudo apt install -y python3-serial || true
  sudo usermod -aG dialout "$USER"
  PKGS="$PKGS ydlidar_ros2_driver robot_lidar"
fi

source "/opt/ros/$DISTRO/setup.bash"
# shellcheck disable=SC2086
colcon build --symlink-install --packages-select $PKGS --cmake-args -DCMAKE_POLICY_VERSION_MINIMUM=3.5

echo
echo "Build done. In EVERY new terminal:"
echo "  source /opt/ros/$DISTRO/setup.bash && source $PWD/install/setup.bash"
echo "Then:  ros2 launch robot_description sim_lite.launch.py        (simulation)"
echo "  or:  ros2 launch robot_lidar lidar.launch.py lidar:=x2       (real lidar; log out/in once first for USB access)"
