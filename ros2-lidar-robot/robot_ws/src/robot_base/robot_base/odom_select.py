"""Chooses who publishes /odom + TF odom -> base_link (used by robot.launch.py and the simulator).

  lidar   rf2o_laser_odometry (scan matching) owns /odom + TF; base_node only drives the motors and
          publishes its wheel estimate on /odom_wheels for comparison. For robots without encoders.
  wheels  base_node owns /odom + TF (encoders, or open loop from the commands).
"""
MODES = ('lidar', 'wheels')


def rf2o_installed():
    try:
        from ament_index_python.packages import get_package_share_directory
        get_package_share_directory('rf2o_laser_odometry')
        return True
    except Exception:          # PackageNotFoundError, or ament_index missing (offline tests)
        return False


def resolve(mode, have_rf2o):
    """-> (effective mode, warning or None)"""
    mode = (mode or 'lidar').strip().lower()
    if mode not in MODES:
        raise ValueError(f"odom must be 'lidar' or 'wheels', not '{mode}'")
    if mode == 'lidar' and not have_rf2o:
        return 'wheels', ('odom:=lidar but rf2o_laser_odometry is not built (run ./setup_pi.sh): '
                          'falling back to wheel odometry')
    return mode, None


def base_node_params(mode):
    """base_node parameter overrides for an effective mode."""
    if mode == 'lidar':
        return {'odom_topic': '/odom_wheels', 'publish_tf': False, 'odom_source': 'lidar'}
    return {'odom_topic': '/odom', 'publish_tf': True}
