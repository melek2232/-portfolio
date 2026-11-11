"""ROS 2 simulation WITHOUT Gazebo: simulated lidar + odometry, slam_toolbox, Nav2, RViz.

  ros2 launch robot_description sim_lite.launch.py
Shows the lidar points (/scan), the map being generated (/map), the robot and its odometry in RViz.

Arguments:
  auto:=false        drive with  ros2 run teleop_twist_keyboard teleop_twist_keyboard
  rviz:=false  slam:=false
  odom:=truth        perfect odometry (default)
  odom:=open_loop    odometry integrated from the commands, like the real robot without encoders
  odom:=lidar        rf2o lidar odometry (robot_base/lidar_odom.launch.py), like the real robot
  slip_linear:=0.9 slip_angular:=0.8   the wheels really move 90 % / turn 80 % of what was asked
  nav:=true          Nav2 on the live SLAM map with the REAL robot's parameters (robot_base config);
                     click 2D Goal Pose in RViz. Implies auto:=false.
The true pose is always on /ground_truth: tools/eval_odom.py measures the odometry drift.
"""
import os
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ODOM_MODES = {'truth': 'truth', 'open_loop': 'open_loop', 'lidar': 'none'}


def _setup(context):
    pkg = get_package_share_directory('robot_description')
    arg = lambda name: LaunchConfiguration(name).perform(context)   # noqa: E731
    odom = arg('odom').strip().lower()
    if odom not in ODOM_MODES:
        raise RuntimeError(f"odom:= must be truth, open_loop or lidar, not '{odom}'")
    nav = arg('nav').lower() == 'true'
    auto = arg('auto').lower() == 'true' and not nav
    with open(os.path.join(pkg, 'urdf', 'robot.urdf')) as f:
        robot_desc = f.read()

    actions = [
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': robot_desc}], output='screen'),
        Node(package='robot_description', executable='fake_robot.py', output='screen',
             parameters=[{'auto': auto, 'odom_mode': ODOM_MODES[odom],
                          'slip_linear': float(arg('slip_linear')),
                          'slip_angular': float(arg('slip_angular'))}]),
    ]
    if odom == 'lidar':
        base = get_package_share_directory('robot_base')
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(base, 'launch', 'lidar_odom.launch.py')),
            launch_arguments={'scan_topic': '/scan'}.items()))
    if arg('slam').lower() == 'true':
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(
                get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py')),
            launch_arguments={'slam_params_file': os.path.join(pkg, 'config', 'slam_sim.yaml'),
                              'use_sim_time': 'false'}.items()))
    if nav:
        from robot_base.nav2_params import build      # the real robot's Nav2 configuration
        base = get_package_share_directory('robot_base')
        nav2 = get_package_share_directory('nav2_bringup')
        overlays = [os.path.join(base, 'config', 'nav2_overrides.yaml')]
        if odom == 'lidar':
            overlays.append(os.path.join(base, 'config', 'nav2_lidar_odom.yaml'))
        params = build(os.path.join(nav2, 'params', 'nav2_params.yaml'), overlays,
                       os.path.join(tempfile.gettempdir(), 'robot_sim_lite_nav2_params.yaml'))
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(nav2, 'launch', 'navigation_launch.py')),
            launch_arguments={'params_file': params, 'use_sim_time': 'false',
                              'autostart': 'true'}.items()))
    if arg('rviz').lower() == 'true':
        actions.append(Node(package='rviz2', executable='rviz2', output='log',
                            arguments=['-d', os.path.join(pkg, 'rviz', 'mapping.rviz')]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('auto', default_value='true',
                              description='true = the robot explores by itself'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('slam', default_value='true'),
        DeclareLaunchArgument('odom', default_value='truth', description='truth | open_loop | lidar'),
        DeclareLaunchArgument('slip_linear', default_value='1.0'),
        DeclareLaunchArgument('slip_angular', default_value='1.0'),
        DeclareLaunchArgument('nav', default_value='false',
                              description='true = Nav2 with the real robot parameters'),
        OpaqueFunction(function=_setup),
    ])
