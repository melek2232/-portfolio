# Robot v2: Raspberry Pi 5 + Arduino Mega + YDLIDAR X2, controlled from a PC

Drive the robot from your PC, watch the **lidar and the map being built live**, let it **explore by itself**,
or **click a goal on the map**. A safety layer sits between every command and the motors.

```
 PC (Docker, ROS 2 Jazzy)                    Raspberry Pi 5 (ROS 2 Jazzy)                     hardware
 ┌────────────────────────┐   Ethernet/Wi-Fi  ┌──────────────────────────────────────────┐
 │ pc/panel.sh            │◄─────────────────►│ ydlidar driver ─► /scan ─► scan_filter ──┼─► slam_toolbox ─► /map
 │  web panel (browser):  │   ROS 2 topics    │                              │           │
 │  map, lidar, drive,    │                   │ PC panel (manual) ─┐         ▼           │
 │  modes, e-stop, goal   │                   │ explorer (explore) ┼─► cmd_mux ─► base_node ─► USB ─► Arduino Mega
 └────────────────────────┘                   │ Nav2 (nav)        ─┘  (mode, e-stop,     │            │ PWM
                                              │                        obstacle stop)    │            ▼
                                              │ health, map_autosave                     │      H-bridge ─► motors
                                              └──────────────────────────────────────────┘
```

* **Modes** (buttons in the panel): `stop`, `manual` (you drive), `explore` (autonomous), `nav` (click-to-go, needs Nav2).
  The robot starts in `manual` and does **not move by itself**.
* **Safety layer** (`cmd_mux`): e-stop latch; a silent source (released key, closed browser, lost link) stops the robot
  after 0.5 s; no lidar data = no motion; speed is reduced near an obstacle and forward motion is blocked at 10 cm
  (ahead or behind, in every mode); speeds are clamped. The Mega also stops the motors by itself after 0.4 s without commands.
* **Lidar odometry** (default, `ODOM=lidar` in `robot.env`): the robot has no encoders and no IMU, so the
  `odom -> base_link` motion comes from scan matching (rf2o) instead of the commanded speeds. Section 6.
* **Better maps**: lidar noise filter (`scan_filter`), `slam_v2.yaml` tuned for this lidar and open-loop odometry,
  loop closing, automatic map backup every 3 minutes (`~/maps/autosave`).
* **Monitoring**: `/robot_health` (lidar rate, Mega link, map age, Pi temperature and memory) shown in the panel,
  `check_system.sh` for a layer-by-layer diagnosis, optional start at boot (`install_service.sh`).

## 1. Install on the Pi (once)
```bash
unzip robot_final.zip && cd robot_ws
./setup_pi.sh                    # installs everything (several minutes), then log out and in
```
Upload the Mega sketch from your PC (Arduino IDE, board Mega 2560, pins in the CONFIG block: `firmware/README.md`),
then test the motors with the robot on blocks: `python3 firmware/tools/arduino_test.py <port>`.
Ports and settings live in **`robot.env`** (already filled with the stable `/dev/serial/by-id/...` names of your devices).

## 2. Install on the PC (once)
Only Docker is needed (RViz and the panel run in a Jazzy container, because the Pi runs Jazzy):
```bash
sudo apt install -y docker.io && sudo usermod -aG docker $USER      # log out and in
docker pull osrf/ros:jazzy-desktop
```
Put the same `robot_ws` folder on the PC (the `pc/` scripts read `robot.env`).

## 3. Every session
**Pi** (SSH, inside `tmux`):  `cd robot_ws && ./run_robot.sh`
**PC**:  `./pc/panel.sh`  then open **http://localhost:8080**

In the panel: pick a mode, drive with the pad or the arrow keys / WASD (hold = move, release = stop, Space = stop,
Esc = e-stop), **Explore** to let it discover the room, **Download map** to save the map.
Click-to-go: `NAV=true ./run_robot.sh`, mode **Navigate**, press **Set goal**, click and drag on the map (position + heading).

Other tools: `./pc/rviz.sh` (RViz), `./pc/teleop_keyboard.sh`, `./pc/mode.sh explore`, `./pc/estop.sh [release]`,
`./check_system.sh` (on the Pi), `./src/robot_base/scripts/save_map.sh my_room` (Nav2 map + pose graph).

## 4. Make it move well: calibration (10 minutes, do it once)
1. Motors too slow or hum: raise `min_duty` in `src/robot_base/config/base.yaml` (try 0.35, 0.40).
2. `./src/robot_base/scripts/calibrate.py straight` → it prints the `max_wheel_speed` to use.
3. `./src/robot_base/scripts/calibrate.py turn` → it prints the `angular_scale` (corrects the odometry SLAM starts from).
4. Restart `./run_robot.sh`. Explorer speed: `SPEED=0.15 ./run_robot.sh` (the safety layer caps everything at 0.20 m/s).
5. Lidar mounted backwards: `LIDAR_YAW=3.14159` in `robot.env`. Wrong turn direction: `invert_left` / `invert_right`.

## 5. Map quality: what matters most
The odometry has no sensor (commanded speeds only), so wheel slip adds error and the map depends on the scan matcher.
It works in rooms with walls and furniture, and degrades in long empty corridors or open halls. In order of effect:
1. **Wheel encoders** (the Mega firmware already supports them: `firmware/README.md`, `use_encoders: true`): the best upgrade.
2. Drive slowly while mapping (0.10 to 0.15 m/s, turns at 0.6 rad/s or less).
3. Calibrate (section 4). 4. A solid lidar mount (no wobble) and a clean window. 5. Close loops: come back to your start point.

## 6. Navigation without encoders or IMU: lidar odometry + Nav2
Nav2 and slam_toolbox need an `odom -> base_link` transform. Without wheel or inertial sensors, base_node can only
integrate the speeds it *asked* for, so every slip becomes a silent position error. With `ODOM=lidar` (default):
```
 /scan_filtered ─► rf2o_laser_odometry ─► /odom + TF odom->base_link ─► slam_toolbox (map->odom) ─► Nav2
 Nav2 /cmd_vel ─► cmd_mux ─► base_node (motors only; its estimate goes to /odom_wheels for comparison)
```
* `setup_pi.sh` downloads rf2o (`fetch_rf2o.sh`, pinned commit, GPL-3.0) and builds it. `ODOM=wheels` restores the old behaviour.
  If rf2o is missing, the launch falls back to wheel odometry and prints a warning.
* Click-to-go: `NAV=true ./run_robot.sh`, mode **Navigate**. Nav2 runs on the live SLAM map (no saved map needed);
  `navigation.launch.py map:=...` uses a saved map + AMCL, also with `odom:=lidar`.
* Nav2 settings: `config/nav2_overrides.yaml` (this robot) + `config/nav2_lidar_odom.yaml` (lidar odometry: slower turns,
  0.6 rad/s, so consecutive X2 scans overlap well; AMCL trusts the odometry more).
* Limits: the lidar must see structure. In a long featureless corridor, or with the lidar blocked, the odometry stalls;
  Nav2's progress checker then aborts the goal rather than driving blind. Glass and mirrors confuse it too.

**Try it in simulation first** (PC, no robot): `./setup_pc.sh --no-lidar`, then
```bash
ros2 launch robot_description sim_lite.launch.py odom:=lidar slip_linear:=0.9 slip_angular:=0.8 nav:=true
ros2 run robot_description nav_goals.py        # 6-goal tour, checked against the simulator's true pose
ros2 run robot_description eval_odom.py        # odometry drift vs /ground_truth (use nav:=false, auto explorer)
```
`odom:=open_loop` simulates the robot without lidar odometry, `odom:=truth` perfect encoders.
Results in simulation (ROS 2 Jazzy, wheels slipping 10 % forward and 20 % in rotation):

| | open-loop odometry | lidar odometry (rf2o) |
|---|---|---|
| Odometry error after 9 m of exploring (90 s) | 2.0 m (21 % of distance) | **0.03 m (0.4 %)**, max 0.12 m |
| Nav2 tour, 6 goals incl. behind a wall unmapped at start | Nav2 reports 6/6, but the robot really ends **1.31 m** off on the last goal | **6/6, real error ≤ 0.13 m** |

The open-loop failure is the dangerous kind: Nav2 believes it arrived. The simulation also exposed three Nav2 configuration
bugs that would have stopped click-to-go on the real robot, now fixed and covered by `test_nav2_odom_config.py`: MPPI refused
to start (`model_dt` shorter than the 10 Hz controller period), the collision monitor waited for a `base_footprint` frame the
robot does not have, and MPPI crawled at 0.05 m/s with this robot's 0.15 m/s limit, so the controller is now Regulated Pure Pursuit (lighter for the Pi).

## 7. Start at boot (optional)
`./install_service.sh` starts `run_robot.sh` at boot in mode `stop`; the robot moves only when you choose a mode in the panel.
`sudo systemctl status robot`, `journalctl -u robot -f`, `./install_service.sh remove`.

## 8. Troubleshooting
| Symptom | Check |
|---|---|
| Panel says "robot silent" | `./run_robot.sh` running? Same `ROS_DOMAIN_ID` in `robot.env`? `./check_system.sh` on the Pi. Direct cable: set `ROS_STATIC_PEERS` in `robot.env`. |
| No USB devices on the Pi, `over-current` in `dmesg` | Pi power supply (official 5 V / 5 A), thin USB-C cable, a short in a device. |
| Robot does not move | Mode is `stop`/`manual` and nothing is held; e-stop active; panel shows the reason (`blind`, `obstacle`, `estop`). |
| Map empty | `ros2 lifecycle get /slam_toolbox` must be `active`; the robot must move; Fixed Frame `map`. |
| Mirrored map / wrong side | `LIDAR_YAW`, `invert_left`, `invert_right`. |
| Nav2 goal aborted "Failed to make progress" | lidar blocked or featureless area (odometry stalls); `ros2 topic hz /odom` must follow the lidar rate. |
| `rf2o_laser_odometry is not built` warning | `./fetch_rf2o.sh` then `./setup_pi.sh` (or set `ODOM=wheels`). |
| Pi and PC on different ROS distributions | Use the Docker scripts (`pc/*.sh`), never a Lyrical RViz against the Jazzy Pi. |

## 9. Tests that were run, and what was not
`./run_all_tests.sh` runs offline (no robot): Mega firmware logic, Pi-Mega serial protocol, base node, motor maths,
command arbitration + safety layer (modes, e-stop, timeouts, obstacle stop, blind lidar), scan filter, health logic,
the robot + safety layer + explorer in a simulated room (0 collisions), the web panel in a real browser (map and lidar
drawing, buttons, keys, goal clicks, security checks), the Nav2 parameter merge against Jazzy's real defaults and the
lidar / wheels odometry selection.
**Run on real ROS 2 Jazzy in simulation** (`sim_lite`): rf2o, slam_toolbox, Nav2 on the live map with the robot's own
parameters, `robot.launch.py` action selection, base_node in lidar mode (results in section 6).
**Not tested on the hardware yet**: rf2o with the real X2 scans, Nav2 click-to-go on the real robot, `pc/*.sh` with Docker,
the systemd service, the calibration script on the robot. Expect small fixes on first run; send the first error lines.
**Safety:** this is a hobby/education robot. The software e-stop and the obstacle stop are not safety-rated and the lidar sees
one plane only (not stairs, low or transparent objects). Fit a physical switch on the motor battery, and do not run it
unattended near people, stairs or edges. "Industrial" use would need certified safety hardware, bumpers or a safety lidar,
and encoders; this project is the software base for that, not that product.

## 10. What else is in the folder
| Folder / file | |
|---|---|
| `firmware/` | Arduino Mega sketch, wiring tables, `arduino_test.py` (motor wiring test), encoder tools |
| `src/robot_base/` | v2 nodes (`cmd_mux`, `scan_filter`, `health`, `map_autosave`, `explore`, `base_node`), launch files, configs |
| `src/robot_lidar/`, `src/ydlidar_ros2_driver/` | lidar launch/config and the YDLIDAR driver (needs the YDLidar SDK: `setup_pi.sh` installs it) |
| `src/robot_description/` | simulation of the robot (Gazebo or `sim_lite.launch.py`), see `setup_pc.sh` |
| `pc_viewer/` | stand-alone lidar viewer without ROS (`python pc_viewer/viewer.py sim` or `live COMx`) |
| `INSTALL_LYRICAL.md` | notes for building the driver with CMake 4 / Lyrical |
| `robot.env` | domain id, ports, lidar yaw, explorer speed, odometry source |
| `fetch_rf2o.sh` | downloads the rf2o lidar odometry (pinned) into `src/` (called by the setup scripts) |
