"""Gazebo + robot + SLAM + RViz, and a self-driving explorer so the map builds by itself.

  ros2 launch robot_description sim.launch.py
Arguments: gui:=false (no Gazebo window), rviz:=false, slam:=false, auto:=false (drive with teleop)
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            OpaqueFunction, SetEnvironmentVariable)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _gazebo(context):
    pkg = get_package_share_directory('robot_description')
    ros_gz_sim = get_package_share_directory('ros_gz_sim')
    world = os.path.join(pkg, 'worlds', 'mapping_room.sdf')
    gui = LaunchConfiguration('gui').perform(context).lower() == 'true'
    gz_args = f'-r -v 2 {world}' if gui else f'-r -s --headless-rendering -v 2 {world}'
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': gz_args}.items())]


def generate_launch_description():
    pkg = get_package_share_directory('robot_description')
    urdf = os.path.join(pkg, 'urdf', 'robot.urdf')
    with open(urdf) as f:
        robot_desc = f.read()

    # lets Gazebo resolve package://robot_description/meshes/...
    old = os.environ.get('GZ_SIM_RESOURCE_PATH', '')
    set_res = SetEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.dirname(pkg) + (os.pathsep + old if old else ''))

    rsp = Node(
        package='robot_state_publisher', executable='robot_state_publisher',
        parameters=[{'robot_description': robot_desc, 'use_sim_time': True}],
        output='screen')

    spawn = Node(
        package='ros_gz_sim', executable='create',
        arguments=['-file', urdf, '-name', 'robot', '-x', '0.0', '-y', '0.0', '-z', '0.1'],
        output='screen')

    bridge = Node(
        package='ros_gz_bridge', executable='parameter_bridge',
        parameters=[{'config_file': os.path.join(pkg, 'config', 'bridge.yaml'),
                     'use_sim_time': True}],
        output='screen')

    relay = Node(
        package='robot_description', executable='scan_relay.py',
        parameters=[{'use_sim_time': True}], output='screen')

    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py')),
        launch_arguments={'slam_params_file': os.path.join(pkg, 'config', 'slam_sim.yaml'),
                          'use_sim_time': 'true'}.items(),
        condition=IfCondition(LaunchConfiguration('slam')))

    wander = Node(
        package='robot_description', executable='wander.py',
        parameters=[{'use_sim_time': True}], output='screen',
        condition=IfCondition(LaunchConfiguration('auto')))

    rviz = Node(
        package='rviz2', executable='rviz2', output='log',
        arguments=['-d', os.path.join(pkg, 'rviz', 'mapping.rviz')],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(LaunchConfiguration('rviz')))

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true', description='show the Gazebo window'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('slam', default_value='true'),
        DeclareLaunchArgument('auto', default_value='true',
                              description='true = the robot explores by itself'),
        set_res,
        OpaqueFunction(function=_gazebo),
        rsp, spawn, bridge, relay, slam, wander, rviz,
    ])
