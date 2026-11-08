"""ROS 2 simulation WITHOUT Gazebo: simulated lidar + odometry, slam_toolbox, RViz.

  ros2 launch robot_description sim_lite.launch.py
Shows the lidar points (/scan), the map being generated (/map), the robot and its odometry in RViz.
Arguments: auto:=false (drive with  ros2 run teleop_twist_keyboard teleop_twist_keyboard), rviz:=false, slam:=false
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('robot_description')
    with open(os.path.join(pkg, 'urdf', 'robot.urdf')) as f:
        robot_desc = f.read()

    rsp = Node(package='robot_state_publisher', executable='robot_state_publisher',
               parameters=[{'robot_description': robot_desc}], output='screen')
    robot = Node(package='robot_description', executable='fake_robot.py', output='screen',
                 parameters=[{'auto': LaunchConfiguration('auto')}])
    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py')),
        launch_arguments={'slam_params_file': os.path.join(pkg, 'config', 'slam_sim.yaml'),
                          'use_sim_time': 'false'}.items(),
        condition=IfCondition(LaunchConfiguration('slam')))
    rviz = Node(package='rviz2', executable='rviz2', output='log',
                arguments=['-d', os.path.join(pkg, 'rviz', 'mapping.rviz')],
                condition=IfCondition(LaunchConfiguration('rviz')))
    return LaunchDescription([
        DeclareLaunchArgument('auto', default_value='true',
                              description='true = the robot explores by itself'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('slam', default_value='true'),
        rsp, robot, slam, rviz])
