"""Build a map: lidar + base + slam_toolbox (+ RViz). Drive with teleop_twist_keyboard.

On the Pi without a screen add rviz:=false and watch the map from your PC."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    base = get_package_share_directory('robot_base')

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

    def make_slam(context):
        # no motors (dry_run) = no odometry: let the scan matcher process every scan
        cfg = 'slam_handheld.yaml' if LaunchConfiguration('backend').perform(context) == 'dry_run' \
            else 'slam_real.yaml'
        # slam_toolbox's own launch file is required: since ROS 2 Jazzy the node is a LIFECYCLE node and
        # must be configured + activated, otherwise it never publishes /map.
        return [IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(
                get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py')),
            launch_arguments={'slam_params_file': os.path.join(base, 'config', cfg),
                              'use_sim_time': 'false', 'autostart': 'true'}.items())]

    slam = OpaqueFunction(function=make_slam)

    explore = Node(
        package='robot_base', executable='explore', name='explore', output='screen',
        parameters=[{'lidar_yaw': LaunchConfiguration('lidar_yaw'),
                     'max_speed': LaunchConfiguration('explore_speed')}],
        condition=IfCondition(LaunchConfiguration('explore')))

    rviz = Node(
        package='rviz2', executable='rviz2', output='log',
        arguments=['-d', os.path.join(base, 'rviz', 'mapping.rviz')],
        condition=IfCondition(LaunchConfiguration('rviz')))

    return LaunchDescription([
        DeclareLaunchArgument('lidar', default_value='x2'),
        DeclareLaunchArgument('port', default_value='/dev/ttyUSB0'),
        DeclareLaunchArgument('backend', default_value='serial'),
        DeclareLaunchArgument('serial_port', default_value='/dev/ttyACM0'),
        DeclareLaunchArgument('lidar_x', default_value='-0.068'),
        DeclareLaunchArgument('lidar_z', default_value='0.12'),
        DeclareLaunchArgument('lidar_yaw', default_value='0.0'),
        DeclareLaunchArgument('odom', default_value='lidar', description='lidar (rf2o) | wheels'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('explore', default_value='false',
                              description='true = the robot discovers the room by itself'),
        DeclareLaunchArgument('explore_speed', default_value='0.12'),
        robot, slam, explore, rviz,
    ])
