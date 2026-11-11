"""v2 bring-up of the whole robot.

  lidar -> scan_filter -> /scan_filtered -> slam_toolbox (map) , cmd_mux (safety)
  PC panel / teleop (/cmd_vel_teleop), explorer (/cmd_vel_auto), Nav2 (/cmd_vel)
        -> cmd_mux (mode, e-stop, obstacle stop) -> /cmd_vel_safe -> base_node -> Arduino Mega

  ros2 launch robot_base bringup.launch.py                       # starts in 'manual': nothing moves by itself
  Arguments: nav:=true (Nav2 click-to-go), odom:=lidar|wheels (default lidar: rf2o, no encoders needed),
             initial_mode:=stop|manual|explore|nav, explore_speed:=0.12,
             lidar_yaw:=3.14159, backend:=dry_run (no motors), rviz:=true, autosave:=false
Change the mode / stop from the PC:  pc/mode.sh manual|explore|nav|stop      pc/estop.sh
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
    cfg = os.path.join(base, 'config', 'robot.yaml')
    lc = LaunchConfiguration
    yaw = float(lc('lidar_yaw').perform(context))
    actions = []

    actions.append(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(base, 'launch', 'robot.launch.py')),
        launch_arguments={'lidar': lc('lidar'), 'port': lc('port'), 'backend': lc('backend'),
                          'serial_port': lc('serial_port'), 'lidar_x': lc('lidar_x'),
                          'lidar_z': lc('lidar_z'), 'lidar_yaw': lc('lidar_yaw'),
                          'cmd_vel_topic': '/cmd_vel_safe', 'odom': lc('odom'),
                          'odom_scan_topic': '/scan_filtered'}.items()))

    actions.append(Node(package='robot_base', executable='scan_filter', name='scan_filter',
                        output='screen', parameters=[cfg]))
    actions.append(Node(package='robot_base', executable='cmd_mux', name='cmd_mux', output='screen',
                        parameters=[cfg, {'initial_mode': lc('initial_mode'), 'lidar_yaw': yaw}]))
    actions.append(Node(package='robot_base', executable='explore', name='explore', output='screen',
                        parameters=[{'lidar_yaw': yaw, 'max_speed': lc('explore_speed')}],
                        remappings=[('/cmd_vel', '/cmd_vel_auto'), ('/scan', '/scan_filtered')]))
    actions.append(Node(package='robot_base', executable='health', name='health', output='screen'))
    actions.append(Node(package='robot_base', executable='map_autosave', name='map_autosave',
                        output='screen', parameters=[cfg], condition=IfCondition(lc('autosave'))))

    # slam_toolbox: its own launch file configures + activates the lifecycle node
    actions.append(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py')),
        launch_arguments={'slam_params_file': os.path.join(base, 'config', 'slam_v2.yaml'),
                          'use_sim_time': 'false', 'autostart': 'true'}.items()))

    if lc('nav').perform(context).lower() == 'true':
        nav2 = get_package_share_directory('nav2_bringup')
        mode, _ = odom_select.resolve(lc('odom').perform(context), odom_select.rf2o_installed())
        overlays = [os.path.join(base, 'config', 'nav2_overrides.yaml')]
        if mode == 'lidar':
            overlays.append(os.path.join(base, 'config', 'nav2_lidar_odom.yaml'))
        params = build(os.path.join(nav2, 'params', 'nav2_params.yaml'), overlays,
                       os.path.join(tempfile.gettempdir(), 'robot_nav2_params.yaml'))
        # Nav2 planner/controller on top of the live SLAM map (no AMCL, no saved map needed)
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(nav2, 'launch', 'navigation_launch.py')),
            launch_arguments={'params_file': params, 'use_sim_time': 'false',
                              'autostart': 'true'}.items()))

    actions.append(Node(package='rviz2', executable='rviz2', output='log',
                        arguments=['-d', os.path.join(base, 'rviz', 'mapping.rviz')],
                        condition=IfCondition(lc('rviz'))))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('lidar', default_value='x2'),
        DeclareLaunchArgument('port', default_value='/dev/ttyUSB0'),
        DeclareLaunchArgument('backend', default_value='serial'),
        DeclareLaunchArgument('serial_port', default_value='/dev/ttyACM0'),
        DeclareLaunchArgument('lidar_x', default_value='-0.068'),
        DeclareLaunchArgument('lidar_z', default_value='0.12'),
        DeclareLaunchArgument('lidar_yaw', default_value='0.0'),
        DeclareLaunchArgument('initial_mode', default_value='manual'),
        DeclareLaunchArgument('explore_speed', default_value='0.12'),
        DeclareLaunchArgument('nav', default_value='false'),
        DeclareLaunchArgument('odom', default_value='lidar', description='lidar (rf2o) | wheels'),
        DeclareLaunchArgument('autosave', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='false'),
        OpaqueFunction(function=_setup),
    ])
