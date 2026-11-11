"""Real robot: lidar + TF (robot_lidar) + base node (Arduino Mega motors) + odometry.

odom:=lidar (default) rf2o lidar odometry publishes /odom + TF, base_node only drives the motors
odom:=wheels          base_node publishes /odom + TF (encoders or open loop), as before
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from robot_base import odom_select


def _setup(context):
    base = get_package_share_directory('robot_base')
    lidar_pkg = get_package_share_directory('robot_lidar')
    lc = LaunchConfiguration
    mode, warning = odom_select.resolve(lc('odom').perform(context), odom_select.rf2o_installed())
    actions = [LogInfo(msg=f'[robot] WARNING {warning}')] if warning else []

    actions.append(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(lidar_pkg, 'launch', 'lidar.launch.py')),
        launch_arguments={'lidar': lc('lidar'), 'port': lc('port'), 'check': 'false',
                          'lidar_x': lc('lidar_x'), 'lidar_z': lc('lidar_z'),
                          'lidar_yaw': lc('lidar_yaw')}.items()))

    actions.append(Node(
        package='robot_base', executable='base_node', name='base_node',
        output='screen', emulate_tty=True,
        parameters=[os.path.join(base, 'config', 'base.yaml'),
                    {'backend': lc('backend'), 'serial_port': lc('serial_port'),
                     'cmd_vel_topic': lc('cmd_vel_topic')},
                    odom_select.base_node_params(mode)]))

    if mode == 'lidar':
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(base, 'launch', 'lidar_odom.launch.py')),
            launch_arguments={'scan_topic': lc('odom_scan_topic')}.items()))
    actions.append(LogInfo(msg=f'[robot] odometry: {mode}'))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('lidar', default_value='x2', description='x4 | x2 | g4'),
        DeclareLaunchArgument('port', default_value='/dev/ttyUSB0',
                              description='serial port of the LIDAR'),
        DeclareLaunchArgument('backend', default_value='serial',
                              description='serial (Arduino Mega) | dry_run (no motors) | gpio'),
        DeclareLaunchArgument('serial_port', default_value='/dev/ttyACM0',
                              description='serial port of the Arduino Mega'),
        DeclareLaunchArgument('cmd_vel_topic', default_value='/cmd_vel',
                              description='topic base_node listens to (bringup uses /cmd_vel_safe)'),
        DeclareLaunchArgument('odom', default_value='lidar',
                              description='lidar (rf2o, no encoders needed) | wheels (base_node)'),
        DeclareLaunchArgument('odom_scan_topic', default_value='/scan',
                              description='scans used by the lidar odometry (bringup: /scan_filtered)'),
        DeclareLaunchArgument('lidar_x', default_value='-0.068'),
        DeclareLaunchArgument('lidar_z', default_value='0.12'),
        DeclareLaunchArgument('lidar_yaw', default_value='0.0'),
        OpaqueFunction(function=_setup),
    ])
