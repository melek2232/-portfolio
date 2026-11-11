"""Lidar odometry with rf2o_laser_odometry: odom -> base_link estimated from consecutive scans.

For a robot WITHOUT encoders or IMU: the wheels' open-loop estimate drifts with every slip, the lidar
sees the walls move and does not. rf2o publishes /odom and the odom -> base_link TF (REP 105), which
is what slam_toolbox and Nav2 need. Started by robot.launch.py when odom:=lidar (the default).

  ros2 launch robot_base lidar_odom.launch.py scan_topic:=/scan_filtered
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    rf2o = Node(
        package='rf2o_laser_odometry', executable='rf2o_laser_odometry_node',
        name='rf2o_laser_odometry', output='screen',
        parameters=[{
            'laser_scan_topic': LaunchConfiguration('scan_topic'),
            'odom_topic': '/odom',
            'publish_tf': True,
            'base_frame_id': 'base_link',
            'odom_frame_id': 'odom',
            'init_pose_from_topic': '',     # start at (0, 0, 0); the default waits for a ground-truth topic
            'freq': ParameterValue(LaunchConfiguration('freq'), value_type=float),
        }])
    return LaunchDescription([
        DeclareLaunchArgument('scan_topic', default_value='/scan',
                              description='laser scans used for odometry (bringup: /scan_filtered)'),
        DeclareLaunchArgument('freq', default_value='20.0',
                              description='processing rate, Hz (>= the lidar scan rate)'),
        rf2o])
