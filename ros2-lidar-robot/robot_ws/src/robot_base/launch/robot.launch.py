"""Real robot: lidar + TF (robot_lidar) + base node (Arduino Mega motors + odometry)."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    base = get_package_share_directory('robot_base')
    lidar_pkg = get_package_share_directory('robot_lidar')

    lidar = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(lidar_pkg, 'launch', 'lidar.launch.py')),
        launch_arguments={
            'lidar': LaunchConfiguration('lidar'),
            'port': LaunchConfiguration('port'),
            'check': 'false',
            'lidar_x': LaunchConfiguration('lidar_x'),
            'lidar_z': LaunchConfiguration('lidar_z'),
            'lidar_yaw': LaunchConfiguration('lidar_yaw'),
        }.items())

    base_node = Node(
        package='robot_base', executable='base_node', name='base_node',
        output='screen', emulate_tty=True,
        parameters=[os.path.join(base, 'config', 'base.yaml'),
                    {'backend': LaunchConfiguration('backend'),
                     'serial_port': LaunchConfiguration('serial_port'),
                     'cmd_vel_topic': LaunchConfiguration('cmd_vel_topic')}])

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
        DeclareLaunchArgument('lidar_x', default_value='-0.068'),
        DeclareLaunchArgument('lidar_z', default_value='0.12'),
        DeclareLaunchArgument('lidar_yaw', default_value='0.0'),
        lidar, base_node,
    ])
