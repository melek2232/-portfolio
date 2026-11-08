"""Nav2 in the simulated room, on a saved map (default: the ideal map of the room).

  ros2 launch robot_description nav.launch.py
  ros2 launch robot_description nav.launch.py map:=$HOME/maps/my_room.yaml
In RViz: the robot starts at the map origin (pose already set); click 2D Goal Pose.
"""
import os
import tempfile

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _merge(base, over):
    for key, val in over.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _merge(base[key], val)
        else:
            base[key] = val
    return base


def _setup(context):
    pkg = get_package_share_directory('robot_description')
    nav2 = get_package_share_directory('nav2_bringup')
    map_arg = LaunchConfiguration('map').perform(context)
    map_file = os.path.expanduser(map_arg) if map_arg else os.path.join(
        pkg, 'maps', 'mapping_room_truth.yaml')
    if not os.path.isfile(map_file):
        raise RuntimeError(f'Map file not found: {map_file}')

    with open(os.path.join(nav2, 'params', 'nav2_params.yaml')) as f:
        params = yaml.safe_load(f)
    with open(os.path.join(pkg, 'config', 'nav2_overrides.yaml')) as f:
        _merge(params, yaml.safe_load(f) or {})
    params_file = os.path.join(tempfile.gettempdir(), 'robot_sim_nav2_params.yaml')
    with open(params_file, 'w') as f:
        yaml.safe_dump(params, f, sort_keys=False)

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg, 'launch', 'sim.launch.py')),
        launch_arguments={'gui': LaunchConfiguration('gui'), 'rviz': 'false',
                          'slam': 'false', 'auto': 'false'}.items())

    bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2, 'launch', 'bringup_launch.py')),
        launch_arguments={'map': map_file, 'params_file': params_file,
                          'use_sim_time': 'true', 'autostart': 'true'}.items())

    rviz = Node(
        package='rviz2', executable='rviz2', output='log',
        arguments=['-d', os.path.join(pkg, 'rviz', 'nav.rviz')],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(LaunchConfiguration('rviz')))
    return [sim, bringup, rviz]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('map', default_value='', description='map .yaml (default: ideal room map)'),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='true'),
        OpaqueFunction(function=_setup),
    ])
