> **Version 2:** the normal way to run the robot is now `./run_robot.sh` (launch `bringup.launch.py`) with the PC
> panel, see the top-level `README.md`. This file documents the individual launch files and the calibration.

# robot_base: Raspberry Pi -> Arduino Mega -> H-bridge robot

`base_node` listens to `/cmd_vel`, sends the left/right PWM to the Mega over USB, and publishes
`/odom` and the `odom -> base_link` transform. Odometry is **open loop** (computed from the
commands) unless you wire encoders (see `firmware/README.md`, then `use_encoders: true`).
SLAM (mapping) and AMCL (navigation) correct the drift with the lidar.

Launch files: `robot.launch.py` (lidar + base), `mapping.launch.py` (+ SLAM + RViz),
`navigation.launch.py` (+ Nav2 on a saved map). Common arguments:

| Argument | Default | |
|---|---|---|
| `lidar` | `x2` | `x2`, `x4` or `g4` |
| `port` | `/dev/ttyUSB0` | lidar serial port |
| `serial_port` | `/dev/ttyACM0` | Arduino Mega serial port |
| `backend` | `serial` | `serial` (Mega), `dry_run` (no motors, PC test), `gpio` (H-bridge on the Pi pins) |
| `lidar_x`, `lidar_z` | `-0.068`, `0.12` | lidar position on the robot (m), **measure yours** |
| `lidar_yaw` | `0.0` | `3.14159` if the lidar's zero angle points to the REAR |
| `rviz` | `true` | `false` on a Pi without screen |

## Step by step
1. Upload the firmware, check the wiring with `firmware/tools/arduino_test.py` (see `firmware/README.md`).
2. **Direction check.** `base_node` drives the robot toward +x for `linear.x > 0`, and the lidar
   zero angle must point the same way. With the lidar's marked front (arrow / cable side) toward
   the way the robot moves, `lidar_yaw` stays 0. If the robot drives toward the lidar's rear, add
   `lidar_yaw:=3.14159`. Check in RViz: driving forward, the wall in front must come closer.
3. Test the motors from ROS (robot on blocks):
   ```bash
   ros2 launch robot_base robot.launch.py serial_port:=/dev/ttyACM0
   ./src/robot_base/scripts/test_motors.sh        # second terminal
   ```
4. **Calibrate** (`config/base.yaml`; `colcon build` is not needed with `--symlink-install`):
   * `min_duty`: raise `0.25` until the robot starts moving reliably at the smallest commands.
   * `max_wheel_speed` = speed at 100 % PWM. Command `linear.x: 0.15` for 5 s on the floor
     (`timeout 5 ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.15}}"`),
     measure the real distance, then `max_wheel_speed = 0.30 * real_distance / expected_distance`.
   * `linear_scale` = real distance / `odom` distance (`ros2 topic echo /odom --field pose.pose.position`).
   * `angular_scale` = real turn / `odom` turn: command `angular.z: 0.6` for a measured time;
     odom yaw = 2 * atan2(orientation.z, orientation.w). Skid-steer is usually below 1 (0.6 to 0.9).
   * `wheel_separation`: measure between the left and right wheel centres.
5. Map:
   ```bash
   ros2 launch robot_base mapping.launch.py lidar:=x2 serial_port:=/dev/ttyACM0
   ros2 run teleop_twist_keyboard teleop_twist_keyboard        # second terminal (i j l k ,)
   ./src/robot_base/scripts/save_map.sh my_room
   ```
   Drive slowly (about 0.1 m/s, teleop speed with `x`/`z` keys), turn slowly, go near every wall,
   come back to the start to close the loop. Slow motion is what keeps an open-loop map clean.
6. Navigate:
   ```bash
   ros2 launch robot_base navigation.launch.py map:=$HOME/maps/my_room.yaml
   ```
   In RViz: **2D Pose Estimate** where the robot really is (drag its heading), wait for the
   particles to gather, then **2D Goal Pose**.

## Robot without screen (Pi) + RViz on your PC
Same Wi-Fi/LAN, same `ROS_DOMAIN_ID` on both (`export ROS_DOMAIN_ID=42`, e.g. in `~/.bashrc`).
On the Pi: `... mapping.launch.py rviz:=false`. On the PC (this workspace built, or just ROS):
`rviz2 -d ~/robot_ws/src/robot_base/rviz/mapping.rviz`. If the PC does not see the topics:
`ros2 topic list` on both, check the firewall (DDS uses UDP) and that both machines have the
same ROS distro.

## Notes and limits
* The X2 lidar sees 8 m; `config/slam_real.yaml` uses `max_laser_range: 8.0`. For an X4 or G4 raise it to
  9.5 / 15 (and the `laser_max_range` of `nav2_overrides.yaml`).
* Open-loop odometry drifts when wheels slip (carpet, fast turns). Encoders fix this: they are the
  best single improvement for the map quality.
* Nav2 starts from `nav2_bringup`'s default parameters plus `config/nav2_overrides.yaml`
  (slow speeds, robot radius 0.16 m). Parameter names can differ slightly between Nav2 releases.
* Safety: the Mega stops the motors 0.4 s after the last command, `base_node` after 0.5 s without
  `/cmd_vel`, and both send a stop when closed. Test new settings on blocks.
* `backend:=gpio` is kept for robots whose H-bridge is wired directly on the Pi; not used here.

## "I only see laser dots, no map"
slam_toolbox only adds a scan when the robot moved (0.05 m / 0.05 rad according to odometry). With
`backend:=dry_run` the odometry says "not moving", so no scan was ever added. `mapping.launch.py` now uses
`config/slam_handheld.yaml` in that case (no minimum travel: every scan is matched). Move the lidar slowly and
level, near walls (a lidar in the middle of an empty hall sees nothing to match). Checks:
`ros2 topic hz /map` (about 1 per second), `ros2 run tf2_tools view_frames` (needs map -> odom -> base_link -> lidar_link).
In RViz: Fixed Frame = `map`, Map display topic `/map`, Reliability Reliable, Durability Transient Local.

**Root cause found (Jazzy/Lyrical):** `async_slam_toolbox_node` is a lifecycle node. Started as a plain node it stays
"unconfigured" and never publishes `/map` (RViz: Map "No map received", width 0). `mapping.launch.py` now uses slam_toolbox's
own launch file, which configures and activates it. Check: `ros2 lifecycle get /slam_toolbox` must say `active`.
