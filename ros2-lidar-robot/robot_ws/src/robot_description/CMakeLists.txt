cmake_minimum_required(VERSION 3.8)
project(robot_description)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY urdf meshes launch rviz config worlds maps
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS scripts/wander.py scripts/scan_relay.py scripts/fake_robot.py scripts/save_map.sh
  tools/offline_check.py tools/make_truth_map.py tools/eval_odom.py tools/nav_goals.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
