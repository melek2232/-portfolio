# Quick install (ROS 2 Lyrical, manual driver)

1. YDLidar SDK (needs CMake < 4):
   sudo apt install -y git build-essential pkg-config python3-venv python3-pip python3-serial
   python3 -m venv ~/.cmake3-venv && ~/.cmake3-venv/bin/pip install "cmake<4"
   git clone https://github.com/YDLIDAR/YDLidar-SDK.git ~/YDLidar-SDK
   mkdir ~/YDLidar-SDK/build && cd ~/YDLidar-SDK/build
   ~/.cmake3-venv/bin/cmake .. && make -j2 && sudo make install && sudo ldconfig
2. Build:
   source /opt/ros/lyrical/setup.bash && cd <this folder>
   colcon build --symlink-install --packages-select robot_description ydlidar_ros2_driver robot_lidar robot_base --cmake-args -DCMAKE_POLICY_VERSION_MINIMUM=3.5
3. USB access: sudo usermod -aG dialout $USER  (then log out/in)
4. Run:
   source /opt/ros/lyrical/setup.bash && source install/setup.bash
   ros2 launch robot_base mapping.launch.py lidar:=x2 port:=/dev/ttyUSB0 backend:=dry_run
