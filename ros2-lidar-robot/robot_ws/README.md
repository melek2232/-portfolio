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

## 6. Start at boot (optional)
`./install_service.sh` starts `run_robot.sh` at boot in mode `stop`; the robot moves only when you choose a mode in the panel.
`sudo systemctl status robot`, `journalctl -u robot -f`, `./install_service.sh remove`.

## 7. Troubleshooting
| Symptom | Check |
|---|---|
| Panel says "robot silent" | `./run_robot.sh` running? Same `ROS_DOMAIN_ID` in `robot.env`? `./check_system.sh` on the Pi. Direct cable: set `ROS_STATIC_PEERS` in `robot.env`. |
| No USB devices on the Pi, `over-current` in `dmesg` | Pi power supply (official 5 V / 5 A), thin USB-C cable, a short in a device. |
| Robot does not move | Mode is `stop`/`manual` and nothing is held; e-stop active; panel shows the reason (`blind`, `obstacle`, `estop`). |
| Map empty | `ros2 lifecycle get /slam_toolbox` must be `active`; the robot must move; Fixed Frame `map`. |
| Mirrored map / wrong side | `LIDAR_YAW`, `invert_left`, `invert_right`. |
| Pi and PC on different ROS distributions | Use the Docker scripts (`pc/*.sh`), never a Lyrical RViz against the Jazzy Pi. |

## 8. Tests that were run, and what was not
`./run_all_tests.sh` runs offline (no robot): Mega firmware logic, Pi-Mega serial protocol, base node, motor maths,
command arbitration + safety layer (modes, e-stop, timeouts, obstacle stop, blind lidar), scan filter, health logic,
the robot + safety layer + explorer in a simulated room (0 collisions), and the web panel in a real browser (map and lidar
drawing, buttons, keys, goal clicks, security checks).
**Not tested** (no ROS, Arduino, motors, lidar or network link were available): the launch files, the real ROS nodes with
real topics and QoS, Nav2 click-to-go (mode `nav`), slam_toolbox results, `pc/*.sh` with Docker, the systemd service, the
calibration script on the robot. Expect small fixes on first run; send the first error lines.
**Safety:** this is a hobby/education robot. The software e-stop and the obstacle stop are not safety-rated and the lidar sees
one plane only (not stairs, low or transparent objects). Fit a physical switch on the motor battery, and do not run it
unattended near people, stairs or edges. "Industrial" use would need certified safety hardware, bumpers or a safety lidar,
and encoders; this project is the software base for that, not that product.

## 9. What else is in the folder
| Folder / file | |
|---|---|
| `firmware/` | Arduino Mega sketch, wiring tables, `arduino_test.py` (motor wiring test), encoder tools |
| `src/robot_base/` | v2 nodes (`cmd_mux`, `scan_filter`, `health`, `map_autosave`, `explore`, `base_node`), launch files, configs |
| `src/robot_lidar/`, `src/ydlidar_ros2_driver/` | lidar launch/config and the YDLIDAR driver (needs the YDLidar SDK: `setup_pi.sh` installs it) |
| `src/robot_description/` | simulation of the robot (Gazebo or `sim_lite.launch.py`), see `setup_pc.sh` |
| `pc_viewer/` | stand-alone lidar viewer without ROS (`python pc_viewer/viewer.py sim` or `live COMx`) |
| `INSTALL_LYRICAL.md` | notes for building the driver with CMake 4 / Lyrical |
| `robot.env` | domain id, ports, lidar yaw, explorer speed |
