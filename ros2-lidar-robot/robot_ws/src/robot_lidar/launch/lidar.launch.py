import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context):
    pkg = get_package_share_directory('robot_lidar')
    model = LaunchConfiguration('lidar').perform(context).lower()
    params = os.path.join(pkg, 'config', f'ydlidar_{model}.yaml')
    port = LaunchConfiguration('port').perform(context)

    driver = Node(
        package='ydlidar_ros2_driver',
        executable='ydlidar_ros2_driver_node',
        name='ydlidar_ros2_driver_node',
        output='screen',
        emulate_tty=True,
        parameters=[params, {'port': port}],
    )

    # Mounting position of the lidar on the robot (same as lidar_joint in robot.urdf)
    tf_lidar = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_lidar',
        arguments=['--x', LaunchConfiguration('lidar_x').perform(context),
                   '--y', '0',
                   '--z', LaunchConfiguration('lidar_z').perform(context),
                   '--roll', '0', '--pitch', '0',
                   '--yaw', LaunchConfiguration('lidar_yaw').perform(context),
                   '--frame-id', 'base_link', '--child-frame-id', 'lidar_link'],
    )

    check = Node(
        package='robot_lidar',
        executable='scan_check',
        output='screen',
        condition=IfCondition(LaunchConfiguration('check')),
    )
    return [driver, tf_lidar, check]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('lidar', default_value='x4',
                              description='x4 | x2 | g4'),
        DeclareLaunchArgument('port', default_value='/dev/ttyUSB0',
                              description='or /dev/ydlidar if the udev rule is installed'),
        DeclareLaunchArgument('check', default_value='true',
                              description='print a 1 Hz health report of /scan'),
        DeclareLaunchArgument('lidar_x', default_value='-0.068',
                              description='lidar position forward of the robot centre (m)'),
        DeclareLaunchArgument('lidar_z', default_value='0.12',
                              description='lidar height above base_link (m)'),
        DeclareLaunchArgument('lidar_yaw', default_value='0.0',
                              description='lidar rotation (rad): 3.14159 if its zero angle '
                                          'points to the REAR of the robot'),
        OpaqueFunction(function=_setup),
    ])
