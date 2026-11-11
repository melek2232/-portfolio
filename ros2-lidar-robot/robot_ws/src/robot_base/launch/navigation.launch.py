"""Navigate on a saved map: lidar + base + Nav2 (map_server, AMCL, planner, controller...).

Usage: ros2 launch robot_base navigation.launch.py map:=$HOME/maps/my_room.yaml
In RViz: 2D Pose Estimate (where the robot is), then 2D Goal Pose.
"""
import os
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from robot_base import odom_select
from robot_base.nav2_params import build


def _setup(context):
    base = get_package_share_directory('robot_base')
    nav2 = get_package_share_directory('nav2_bringup')
    map_file = os.path.expanduser(LaunchConfiguration('map').perform(context))
    if not os.path.isfile(map_file):
        raise RuntimeError(f'Map file not found: {map_file}  (save one with save_map.sh first)')

    mode, _ = odom_select.resolve(LaunchConfiguration('odom').perform(context),
                                  odom_select.rf2o_installed())
    overlays = [os.path.join(base, 'config', 'nav2_overrides.yaml')]
    if mode == 'lidar':
        overlays.append(os.path.join(base, 'config', 'nav2_lidar_odom.yaml'))
    params = build(os.path.join(nav2, 'params', 'nav2_params.yaml'), overlays,
                   os.path.join(tempfile.gettempdir(), 'robot_nav2_params.yaml'))

    robot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(base, 'launch', 'robot.launch.py')),
        launch_arguments={'lidar': LaunchConfiguration('lidar'),
                          'port': LaunchConfiguration('port'),
                          'backend': LaunchConfiguration('backend'),
                          'serial_port': LaunchConfiguration('serial_port'),
                          'lidar_x': LaunchConfiguration('lidar_x'),
                          'lidar_z': LaunchConfiguration('lidar_z'),
                          'lidar_yaw': LaunchConfiguration('lidar_yaw'),
                          'odom': LaunchConfiguration('odom')}.items())

    bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2, 'launch', 'bringup_launch.py')),
        launch_arguments={'map': map_file,
                          'params_file': params,
                          'use_sim_time': 'false',
                          'autostart': 'true'}.items())

    rviz = Node(
        package='rviz2', executable='rviz2', output='log',
        arguments=['-d', os.path.join(base, 'rviz', 'navigation.rviz')],
        condition=IfCondition(LaunchConfiguration('rviz')))
    return [robot, bringup, rviz]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('map', description='full path of the map .yaml'),
        DeclareLaunchArgument('lidar', default_value='x2'),
        DeclareLaunchArgument('port', default_value='/dev/ttyUSB0'),
        DeclareLaunchArgument('backend', default_value='serial'),
        DeclareLaunchArgument('serial_port', default_value='/dev/ttyACM0'),
        DeclareLaunchArgument('lidar_x', default_value='-0.068'),
        DeclareLaunchArgument('lidar_z', default_value='0.12'),
        DeclareLaunchArgument('lidar_yaw', default_value='0.0'),
        DeclareLaunchArgument('odom', default_value='lidar', description='lidar (rf2o) | wheels'),
        DeclareLaunchArgument('rviz', default_value='true'),
        OpaqueFunction(function=_setup),
    ])
