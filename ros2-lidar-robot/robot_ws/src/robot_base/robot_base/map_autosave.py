"""Saves the map every few minutes (so a crash or a power cut does not lose it).
Files: ~/maps/autosave/map_<time>.pgm/.yaml (the last `keep` are kept) and latest.pgm/.yaml."""
import glob
import os
import shutil
import subprocess
import time

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


def prune(directory, keep):
    files = sorted(glob.glob(os.path.join(directory, 'map_*.yaml')))
    for old in files[:-keep] if keep > 0 else []:
        for ext in ('.yaml', '.pgm'):
            try:
                os.remove(old[:-5] + ext)
            except OSError:
                pass


class MapAutosave(Node):
    def __init__(self):
        super().__init__('map_autosave')
        self.declare_parameter('interval_s', 180.0)
        self.declare_parameter('directory', '~/maps/autosave')
        self.declare_parameter('keep', 10)
        self.dir = os.path.expanduser(self.get_parameter('directory').value)
        os.makedirs(self.dir, exist_ok=True)
        self.new_map = False
        self.proc = None
        self.prefix = None
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, '/map', self.on_map, qos)
        self.create_timer(float(self.get_parameter('interval_s').value), self.save)
        self.create_timer(1.0, self.poll)

    def on_map(self, msg):
        self.new_map = True

    def save(self):
        if not self.new_map or self.proc is not None:
            return
        self.new_map = False
        self.prefix = os.path.join(self.dir, time.strftime('map_%Y%m%d_%H%M%S'))
        self.proc = subprocess.Popen(
            ['ros2', 'run', 'nav2_map_server', 'map_saver_cli', '-f', self.prefix,
             '--ros-args', '-p', 'save_map_timeout:=8.0'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def poll(self):
        if self.proc is None or self.proc.poll() is None:
            return
        ok = self.proc.returncode == 0 and os.path.exists(self.prefix + '.yaml')
        self.proc = None
        if ok:
            for ext in ('.yaml', '.pgm'):
                shutil.copyfile(self.prefix + ext, os.path.join(self.dir, 'latest' + ext))
            prune(self.dir, int(self.get_parameter('keep').value))
            self.get_logger().info(f'map saved: {self.prefix}.yaml')
        else:
            self.get_logger().warning('autosave failed (is nav2_map_server installed?)')


def main():
    rclpy.init()
    node = MapAutosave()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
